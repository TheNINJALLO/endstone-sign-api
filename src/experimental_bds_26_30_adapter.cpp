#include "endstone_sign/experimental_bds_26_30_adapter.h"

#include "endstone_sign/internal/experimental_runtime_identity.h"
#include "endstone_sign/native_binary_identity.h"
#include "endstone_sign/placement.h"

#include <endstone/endstone.hpp>

#include "bedrock/world/actor/player/player.h"
#include "bedrock/world/level/block/actor/block_actor.h"
#include "bedrock/world/level/block/actor/vanilla_block_actor.h"
#include "bedrock/world/level/block_source.h"
#include "endstone/block/block_type.h"
#include "endstone/core/level/dimension.h"
#include "endstone/core/player.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <exception>
#include <limits>
#include <memory>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <vector>

#if defined(__linux__)
#include <link.h>
#endif

namespace endstone_sign {
namespace {

std::string_view canonicalBdsBuild(std::string_view build) noexcept {
    if (build.starts_with("1."))
        build.remove_prefix(2);
    if (build == "26.33.1")
        return "26.33";
    return build;
}

bool validIdentifierList(std::string_view value) noexcept {
    if (value.empty() || value.front() == '.' || value.back() == '.')
        return false;
    bool previous_dot = false;
    for (const char current : value) {
        if (current == '.') {
            if (previous_dot)
                return false;
            previous_dot = true;
            continue;
        }
        if (!std::isalnum(static_cast<unsigned char>(current)) && current != '-')
            return false;
        previous_dot = false;
    }
    return true;
}

bool expectedEndstoneVersion(std::string_view runtime) noexcept {
    constexpr std::string_view Expected = "0.11.6";
    if (runtime.starts_with('v'))
        runtime.remove_prefix(1);
    if (runtime == Expected)
        return true;
    if (!runtime.starts_with(Expected))
        return false;
    auto suffix = runtime.substr(Expected.size());
    if (suffix.starts_with('+'))
        return validIdentifierList(suffix.substr(1));
    if (!suffix.starts_with(".dev"))
        return false;
    suffix.remove_prefix(4);
    const auto metadata = suffix.find('+');
    const auto serial = suffix.substr(0, metadata);
    if (serial.empty() || !std::ranges::all_of(serial, [](const char current) {
            return current >= '0' && current <= '9';
        })) {
        return false;
    }
    return metadata == std::string_view::npos || validIdentifierList(suffix.substr(metadata + 1));
}

bool exactRuntime(const endstone::Server &server) noexcept {
    try {
        return canonicalBdsBuild(server.getMinecraftVersion()) == "26.33" &&
               expectedEndstoneVersion(server.getVersion());
    } catch (...) {
        return false;
    }
}

class ExperimentalLinuxTextBridge {
  public:
    static constexpr std::size_t SafeTransferredMessageBytes = 22;

    ExperimentalLinuxTextBridge() { initialize(); }

    [[nodiscard]] bool executableIdentityMatch() const noexcept {
        return executable_identity_match_;
    }

    [[nodiscard]] bool ready() const noexcept { return ready_; }

    [[nodiscard]] bool compatibleActor(const BlockActor &actor) const noexcept {
        if (!ready_)
            return false;
        std::uintptr_t vtable{};
        std::memcpy(&vtable, std::addressof(actor), sizeof(vtable));
        return vtable == image_base_ + SignBlockActorVtableRva ||
               vtable == image_base_ + HangingSignBlockActorVtableRva;
    }

    [[nodiscard]] const std::string &failure() const noexcept { return failure_; }

    [[nodiscard]] std::string rawMessage(const BlockActor &actor, const SignSide side) const {
        requireCompatible(actor);
        const auto &message =
            get_raw_message_(&actor, static_cast<std::int32_t>(side));
        if (message.size() > 16 * 1024)
            throw std::runtime_error("native sign message exceeds the safety limit");
        return message;
    }

    [[nodiscard]] std::string ownerXuid(const BlockActor &actor, const SignSide side) const {
        requireCompatible(actor);
        constexpr std::size_t OwnerOffset = 0x120;
        const auto *text = sideText(actor, side);
        const auto &owner =
            *reinterpret_cast<const std::string *>(text + OwnerOffset);
        if (owner.size() > 128 || owner.find('\0') != std::string::npos ||
            !isValidUtf8(owner))
            throw std::runtime_error("native sign text owner failed validation");
        return owner;
    }

    [[nodiscard]] bool plainMessage(const BlockActor &actor, const SignSide side) const {
        requireCompatible(actor);
        return is_string_message_(&actor, static_cast<std::int32_t>(side));
    }

    [[nodiscard]] bool filteredMessageEmpty(const BlockActor &actor,
                                            const SignSide side) const {
        requireCompatible(actor);
        constexpr std::size_t FilteredMessageOffset = 0x18;
        const auto *text = sideText(actor, side);
        const auto &filtered = *reinterpret_cast<const std::string *>(
            text + FilteredMessageOffset);
        return filtered.empty();
    }

    void setMessage(BlockActor &actor, const SignSide side, std::string message,
                    std::string owner_xuid) const {
        requireCompatible(actor);
        if (message.size() > SafeTransferredMessageBytes ||
            owner_xuid.size() > SafeTransferredMessageBytes) {
            throw std::invalid_argument(
                "native text boundary refuses non-SSO message or owner storage");
        }
        std::string canonical_message(message.data(), message.size());
        std::string canonical_owner(owner_xuid.data(), owner_xuid.size());
        if (!usesExpectedSso(canonical_message) ||
            !usesExpectedSso(canonical_owner)) {
            throw std::runtime_error(
                "native text boundary could not canonicalize libc++ SSO storage");
        }
        set_message_(&actor, static_cast<std::int32_t>(side),
                     std::move(canonical_message), std::move(canonical_owner));
    }

  private:
    using GetRawMessage = const std::string &(*)(const BlockActor *, std::int32_t);
    using IsStringMessage = bool (*)(const BlockActor *, std::int32_t);
    using SetMessage =
        void (*)(BlockActor *, std::int32_t, std::string, std::string);

    static constexpr std::uintptr_t SignBlockActorVtableRva = 0x0DCF6BA8;
    static constexpr std::uintptr_t HangingSignBlockActorVtableRva = 0x0DCFC968;

#if defined(__linux__) && defined(__x86_64__)
    static constexpr std::uintptr_t SetMessageRva = 0x0BE10920;
    static constexpr std::size_t SetMessageSize = 274;
    static constexpr std::string_view SetMessageSha256 =
        "b34cee2dde17211f9601e9a915ed0359664069d2ea33f66d762122155a092b4e";
    static constexpr std::uintptr_t GetRawMessageRva = 0x0BE10A80;
    static constexpr std::size_t GetRawMessageSize = 121;
    static constexpr std::string_view GetRawMessageSha256 =
        "1ddeb1780bbd0aab92e0807cfbc6aacefc10d74d0a83e17cf547e30dd1a75f03";
    static constexpr std::uintptr_t IsStringMessageRva = 0x0BE10A60;
    static constexpr std::size_t IsStringMessageSize = 27;
    static constexpr std::string_view IsStringMessageSha256 =
        "a4858fb54d1b9b1dc09cf28288d22cea7a2666e9925dbb70eac85d5dba7adbfc";

    struct MainImageSearch {
        std::optional<std::uintptr_t> base;
    };

    [[nodiscard]] static bool segmentContains(
        const std::uintptr_t segment_begin, const std::uintptr_t segment_size,
        const std::uintptr_t candidate_begin, const std::size_t candidate_size) noexcept {
        if (segment_size > std::numeric_limits<std::uintptr_t>::max() - segment_begin)
            return false;
        const auto segment_end = segment_begin + segment_size;
        if (candidate_size > std::numeric_limits<std::uintptr_t>::max() - candidate_begin)
            return false;
        const auto candidate_end = candidate_begin + candidate_size;
        return candidate_begin >= segment_begin && candidate_end <= segment_end;
    }

    static int findMainExecutable(dl_phdr_info *info, std::size_t, void *opaque) {
        if (info->dlpi_name && info->dlpi_name[0] != '\0')
            return 0;
        const auto base = static_cast<std::uintptr_t>(info->dlpi_addr);
        const auto set_address = base + SetMessageRva;
        const auto get_address = base + GetRawMessageRva;
        const auto string_message_address = base + IsStringMessageRva;
        bool contains_set = false;
        bool contains_get = false;
        bool contains_string_message = false;
        for (std::size_t index = 0; index < info->dlpi_phnum; ++index) {
            const auto &header = info->dlpi_phdr[index];
            if (header.p_type != PT_LOAD || (header.p_flags & PF_X) == 0)
                continue;
            const auto segment_begin = base + header.p_vaddr;
            contains_set = contains_set ||
                           segmentContains(segment_begin, header.p_memsz, set_address,
                                           SetMessageSize);
            contains_get = contains_get ||
                           segmentContains(segment_begin, header.p_memsz, get_address,
                                           GetRawMessageSize);
            contains_string_message =
                contains_string_message ||
                segmentContains(segment_begin, header.p_memsz,
                                string_message_address, IsStringMessageSize);
        }
        if (!contains_set || !contains_get || !contains_string_message)
            return 0;
        static_cast<MainImageSearch *>(opaque)->base = base;
        return 1;
    }

    [[nodiscard]] static bool functionHashMatches(
        const std::uintptr_t address, const std::size_t size,
        const std::string_view expected) {
        const auto bytes = std::span<const std::byte>(
            reinterpret_cast<const std::byte *>(address), size);
        return sha256Bytes(bytes) == expected;
    }
#endif

    [[nodiscard]] static bool usesExpectedSso(const std::string &value) noexcept {
        if (value.size() > SafeTransferredMessageBytes)
            return false;
        const auto object = reinterpret_cast<std::uintptr_t>(
            std::addressof(value));
        const auto data = reinterpret_cast<std::uintptr_t>(value.data());
        std::uint8_t tag{};
        std::memcpy(&tag, std::addressof(value), sizeof(tag));
        return data == object + 1 &&
               tag == static_cast<std::uint8_t>(value.size() * 2);
    }

    void initialize() {
#if defined(__linux__) && defined(__x86_64__)
        if (internal::ExperimentalManifestPlatform != "linux-x64" ||
            internal::ExperimentalBdsPackageVersion != "1.26.33.1" ||
            internal::ExperimentalRuntimeBdsVersion != "26.33" ||
            internal::ExperimentalExecutableSha256.empty() ||
            internal::ExperimentalExecutableSize == 0) {
            failure_ = "experimental Linux manifest identity is incomplete";
            return;
        }
        const std::string empty_string;
        const std::string maximum_short_string(SafeTransferredMessageBytes, 'x');
        const std::string first_long_string(SafeTransferredMessageBytes + 1, 'x');
        const auto object_begin = reinterpret_cast<std::uintptr_t>(
            std::addressof(maximum_short_string));
        const auto object_end = object_begin + sizeof(maximum_short_string);
        const auto short_data = reinterpret_cast<std::uintptr_t>(
            maximum_short_string.data());
        const auto long_begin = reinterpret_cast<std::uintptr_t>(
            std::addressof(first_long_string));
        const auto long_end = long_begin + sizeof(first_long_string);
        const auto long_data = reinterpret_cast<std::uintptr_t>(
            first_long_string.data());
        std::uint8_t empty_tag{};
        std::uint8_t short_tag{};
        std::uint8_t long_tag{};
        std::memcpy(&empty_tag, std::addressof(empty_string), sizeof(empty_tag));
        std::memcpy(&short_tag, std::addressof(maximum_short_string),
                    sizeof(short_tag));
        std::memcpy(&long_tag, std::addressof(first_long_string),
                    sizeof(long_tag));
        if (sizeof(std::string) != 24 || short_data != object_begin + 1 ||
            short_data >= object_end ||
            (long_data >= long_begin && long_data < long_end) || empty_tag != 0 ||
            short_tag != static_cast<std::uint8_t>(
                             SafeTransferredMessageBytes * 2) ||
            (long_tag & 1u) == 0) {
            failure_ = "plugin libc++ string/SSO ABI does not match the exact server";
            return;
        }

        const auto identity = inspectCurrentProcessExecutable();
        if (!identity.ok()) {
            failure_ = "could not inspect /proc/self/exe: " + identity.error;
            return;
        }
        if (identity.size != internal::ExperimentalExecutableSize ||
            identity.sha256 != internal::ExperimentalExecutableSha256) {
            failure_ = "running executable does not match the selected exact manifest";
            return;
        }
        executable_identity_match_ = true;

        MainImageSearch image;
        dl_iterate_phdr(&findMainExecutable, &image);
        if (!image.base) {
            failure_ = "could not locate the exact Sign functions in an executable segment";
            return;
        }
        const auto set_address = *image.base + SetMessageRva;
        const auto get_address = *image.base + GetRawMessageRva;
        const auto string_message_address = *image.base + IsStringMessageRva;
        if (!functionHashMatches(set_address, SetMessageSize, SetMessageSha256) ||
            !functionHashMatches(get_address, GetRawMessageSize,
                                 GetRawMessageSha256) ||
            !functionHashMatches(string_message_address, IsStringMessageSize,
                                 IsStringMessageSha256)) {
            failure_ = "exact Sign text function fingerprint mismatch";
            return;
        }

        set_message_ = reinterpret_cast<SetMessage>(set_address);
        get_raw_message_ = reinterpret_cast<GetRawMessage>(get_address);
        is_string_message_ =
            reinterpret_cast<IsStringMessage>(string_message_address);
        image_base_ = *image.base;
        ready_ = true;
        failure_.clear();
#else
        failure_ = "the exact text probe bridge is currently available only on Linux x64";
#endif
    }

    void requireReady() const {
        if (!ready_)
            throw std::runtime_error(failure_.empty() ? "native text gate is closed"
                                                      : failure_);
    }

    void requireCompatible(const BlockActor &actor) const {
        requireReady();
        if (!compatibleActor(actor))
            throw std::runtime_error("native sign actor vtable fingerprint mismatch");
    }

    [[nodiscard]] const std::byte *sideText(const BlockActor &actor,
                                            const SignSide side) const {
        constexpr std::size_t FrontTextOffset = 0xC8;
        constexpr std::size_t BackTextOffset = 0xD0;
        const auto *actor_bytes = reinterpret_cast<const std::byte *>(&actor);
        const auto text_offset =
            side == SignSide::Front ? FrontTextOffset : BackTextOffset;
        const std::byte *text{};
        std::memcpy(&text, actor_bytes + text_offset, sizeof(text));
        if (!text)
            throw std::runtime_error("exact SignBlockActor side text pointer is null");
        return text;
    }

    GetRawMessage get_raw_message_{};
    IsStringMessage is_string_message_{};
    SetMessage set_message_{};
    std::uintptr_t image_base_{};
    bool executable_identity_match_{};
    bool ready_{};
    std::string failure_;
};

endstone::BlockStates toEndstoneStates(const SignStates &states) {
    endstone::BlockStates result;
    result.reserve(states.size());
    for (const auto &[key, value] : states) {
        std::visit(
            [&result, &key](const auto &entry) {
                using T = std::decay_t<decltype(entry)>;
                if constexpr (std::is_same_v<T, std::int32_t>) {
                    result.insert_or_assign(key, static_cast<int>(entry));
                } else {
                    result.insert_or_assign(key, entry);
                }
            },
            value);
    }
    return result;
}

struct RegisteredBlockData {
    bool type_registered{};
    std::unique_ptr<endstone::BlockData> data;
};

RegisteredBlockData createRegisteredBlockData(
    const endstone::Server &server,
    const std::string &identifier,
    const SignStates &states) {
    const auto registry_name = std::string(endstone::BlockType::RegistryType);
    const auto *untyped_registry = server._getRegistry(registry_name);
    if (!untyped_registry)
        return {};

    const auto *registry =
        static_cast<const endstone::Registry<endstone::BlockType> *>(untyped_registry);
    // Endstone 0.11.6 declares Registry::get noexcept, but its BlockType
    // cache-miss specialization throws. Calling get with an absent ID would
    // therefore terminate the process before this plugin could return an
    // InvalidPatch. forEach only visits identifiers already present in the
    // pre-populated BlockType cache, so an absent requested ID remains an
    // ordinary false result.
    const auto expected_id = endstone::BlockTypeId(identifier);
    bool type_registered = false;
    registry->forEach([&expected_id, &type_registered](const endstone::BlockType &type) {
        if (type.getId() != expected_id)
            return true;
        type_registered = true;
        return false;
    });
    if (!type_registered)
        return {};

    return {
        true,
        server.createBlockData(identifier, toEndstoneStates(states)),
    };
}

SignStates fromEndstoneStates(const endstone::BlockStates &states) {
    SignStates result;
    for (const auto &[key, value] : states) {
        std::visit(
            [&result, &key](const auto &entry) {
                using T = std::decay_t<decltype(entry)>;
                if constexpr (std::is_same_v<T, int>) {
                    result.insert_or_assign(key, static_cast<std::int32_t>(entry));
                } else {
                    result.insert_or_assign(key, entry);
                }
            },
            value);
    }
    return result;
}

bool defaultText(const SignText &text) noexcept {
    return std::ranges::all_of(text.lines, [](const std::string &line) { return line.empty(); }) &&
           text.filtered_message.empty() && text.text_object.empty() &&
           !text.message_is_text_object && text.argb == 0xFF000000u && !text.glowing &&
           !text.hide_glow_outline && text.persist_formatting && text.owner_xuid.empty();
}

bool requiresSignNbt(const SignPlaceRequest &request) noexcept {
    return !defaultText(request.front) || !defaultText(request.back) || request.waxed ||
           request.locked_for_editing_by != -1 || request.locked_for_editing_xuid.has_value() ||
           request.remote_profanity_filter_enabled || request.local_profanity_filter_enabled;
}

bool requiresUnverifiedTextFields(const SignTextPatch &patch) noexcept {
    return patch.filtered_message.has_value() || patch.text_object.has_value() ||
           patch.message_is_text_object.has_value() || patch.argb.has_value() ||
           patch.glowing.has_value() || patch.hide_glow_outline.has_value() ||
           patch.persist_formatting.has_value() || patch.owner_xuid.has_value();
}

bool requiresSignNbt(const SignPatch &patch) noexcept {
    return (patch.front && requiresUnverifiedTextFields(*patch.front)) ||
           (patch.back && requiresUnverifiedTextFields(*patch.back)) ||
           patch.waxed.has_value() || patch.locked_for_editing_by.has_value() ||
           patch.locked_for_editing_xuid.has_value() ||
           patch.remote_profanity_filter_enabled.has_value() ||
           patch.local_profanity_filter_enabled.has_value();
}

bool requestsPlainText(const SignPatch &patch) noexcept {
    return patch.front.has_value() || patch.back.has_value();
}

bool requestsStructuralChange(const SignPatch &patch) noexcept {
    return patch.block_identifier.has_value() || !patch.state_updates.empty() ||
           !patch.state_removals.empty();
}

struct PublicBlockAccess {
    endstone::Dimension *dimension{};
    std::unique_ptr<endstone::Block> block;
    std::unique_ptr<endstone::BlockData> data;
};

std::optional<PublicBlockAccess> locatePublicBlock(endstone::Server &server,
                                                   const SignLocation &location) {
    auto *level = server.getLevel();
    auto *dimension = level ? level->getDimension(location.dimension) : nullptr;
    if (!dimension)
        return std::nullopt;
    auto block = dimension->getBlockAt(location.x, location.y, location.z);
    if (!block)
        return std::nullopt;
    auto data = block->getData();
    if (!data)
        return std::nullopt;
    return PublicBlockAccess{dimension, std::move(block), std::move(data)};
}

struct NativeSignActorAccess {
    BlockSource *source{};
    BlockActor *actor{};
    IVanillaMainBlockActorComponent *main{};
};

struct NativeSignActorLookup {
    std::optional<NativeSignActorAccess> access;
    SignActorStatus status{SignActorStatus::AdapterError};
};

NativeSignActorLookup locateNativeSignActor(
    endstone::Server &server, const SignLocation &location,
    const ExperimentalLinuxTextBridge *exact_text_bridge = nullptr) {
    auto *level = server.getLevel();
    auto *dimension = level ? level->getDimension(location.dimension) : nullptr;
    if (!dimension)
        return {{}, SignActorStatus::ChunkUnavailable};

    // Endstone v0.11.6 constructs every public Dimension as this exact type.
    // This is the same pinned private boundary used by the BlockData adapter.
    auto *exact_dimension = static_cast<endstone::core::EndstoneDimension *>(dimension);
    auto &native_dimension = exact_dimension->getHandle();
    auto &source = native_dimension.getBlockSourceFromMainChunkSource();
    const ::BlockPos position(location.x, location.y, location.z);
    auto *actor = const_cast<BlockActor *>(source.getBlockEntity(position));
    if (!actor)
        return {{}, SignActorStatus::NoBlockActor};
    if (exact_text_bridge && exact_text_bridge->ready() &&
        !exact_text_bridge->compatibleActor(*actor)) {
        return {{}, SignActorStatus::SymbolGateClosed};
    }
    if (actor->getType() != BlockActorType::Sign &&
        actor->getType() != BlockActorType::HangingSign) {
        return {{}, SignActorStatus::WrongBlockActorType};
    }

    // Both allowlisted values are VanillaBlockActor implementations in the
    // pinned v0.11.6 ABI. Let C++ perform the multiple-inheritance adjustment.
    auto *vanilla = static_cast<VanillaBlockActor *>(actor);
    auto *main = static_cast<IVanillaMainBlockActorComponent *>(vanilla);
    if (main->getBlockActorType() != actor->getType()) {
        return {{}, SignActorStatus::WrongBlockActorType};
    }
    return {NativeSignActorAccess{&source, actor, main}, SignActorStatus::Captured};
}

void signalActorChanged(NativeSignActorAccess &access) {
    access.main->setChanged();
    access.main->onChanged(*access.source);
    access.source->fireBlockEntityChanged(*access.actor);
}

SignApplyResult runtimeMismatch() {
    return {
        SignApplyStatus::RuntimeMismatch,
        "experimental Sign adapter requires BDS 1.26.33.1/26.33 with Endstone "
        "0.11.6",
        0,
    };
}

SignApplyResult binaryIdentityMismatch(const std::uint64_t revision = 0) {
    return {
        SignApplyStatus::BinaryIdentityMismatch,
        "structural Sign mutation requires the exact BDS executable SHA-256 "
        "selected by the experimental manifest",
        revision,
    };
}

SignApplyResult nbtUnsupported(const std::uint64_t revision) {
    return {
        SignApplyStatus::Unsupported,
        "filtered/text-object/color/glow/outline/formatting/owner, wax, profanity, "
        "and editor-lock mutation remain behind the unverified SignBlockActor NBT "
        "boundary",
        revision,
    };
}

SignApplyResult textGateClosed(const ExperimentalLinuxTextBridge &bridge,
                               const std::uint64_t revision) {
    return {
        bridge.executableIdentityMatch() ? SignApplyStatus::SymbolValidationFailed
                                         : SignApplyStatus::BinaryIdentityMismatch,
        "exact Linux plain-text bridge is closed: " + bridge.failure(),
        revision,
    };
}

class ExperimentalBds2630SignAdapter final : public ISignAdapter {
  public:
    explicit ExperimentalBds2630SignAdapter(endstone::Server &server)
        : server_(server), exact_runtime_(exactRuntime(server)) {}

    [[nodiscard]] std::string_view name() const noexcept override {
        if (!exact_runtime_)
            return "bds-1.26.33.1-experimental-runtime-mismatch";
        if (text_bridge_.ready())
            return "bds-1.26.33.1-experimental-linux-plain-text";
        if (!text_bridge_.executableIdentityMatch())
            return "bds-1.26.33.1-experimental-binary-identity-gate";
        return "bds-1.26.33.1-experimental-text-symbol-gate";
    }

    [[nodiscard]] SignCapabilities capabilities() const noexcept override {
        SignCapabilities result;
        const bool structural_mutation_gate =
            exact_runtime_ && text_bridge_.executableIdentityMatch();
        result.capture = structural_mutation_gate;
        result.place = structural_mutation_gate;   // Blank signs only.
        result.remove = structural_mutation_gate;  // No item drop.
        result.replace = false; // Pending hosted rollback and replacement validation.
        result.open_editor = structural_mutation_gate; // UI dispatch only.
        result.api_edit_events = structural_mutation_gate;
        result.client_updates = structural_mutation_gate;
        result.exact_build_match = exact_runtime_;

        // This deliberately advertises only the exact, readback-checked subset.
        // The complete-control gate remains closed until the hosted stage probe
        // and the remaining SignBlockActor boundaries are verified.
        result.read_text = exact_runtime_ && text_bridge_.ready();
        result.write_text = exact_runtime_ && text_bridge_.ready();
        result.front_and_back = exact_runtime_ && text_bridge_.ready();
        result.per_line_write = exact_runtime_ && text_bridge_.ready();
        result.editor_lock = false;
        result.restart_persistence = false;
        result.exact_binary_hash_match =
            exact_runtime_ && text_bridge_.executableIdentityMatch();
        result.symbols_validated = false;
        result.stage_probe_passed = false;
        return result;
    }

    [[nodiscard]] std::optional<SignSnapshot> capture(const SignLocation &location) override {
        if (!exact_runtime_ || !text_bridge_.executableIdentityMatch() ||
            !server_.isPrimaryThread())
            return std::nullopt;
        try {
            auto access = locatePublicBlock(server_, location);
            if (!access || !isVanillaSignIdentifier(access->data->getType())) {
                return std::nullopt;
            }

            SignSnapshot snapshot;
            snapshot.location = location;
            snapshot.block_identifier = access->data->getType();
            snapshot.states = fromEndstoneStates(access->data->getBlockStates());
            snapshot.kind = classifySign(snapshot.block_identifier, snapshot.states);

            const auto native =
                locateNativeSignActor(server_, location, &text_bridge_);
            if (!native.access) {
                snapshot.actor_status = native.status;
            } else if (!text_bridge_.ready()) {
                snapshot.actor_status = SignActorStatus::SymbolGateClosed;
            } else {
                std::string error;
                const auto front_message =
                    text_bridge_.rawMessage(*native.access->actor, SignSide::Front);
                const auto back_message =
                    text_bridge_.rawMessage(*native.access->actor, SignSide::Back);
                const auto front_lines = splitSignMessage(front_message, &error);
                if (!front_lines)
                    throw std::runtime_error("front sign text readback failed: " + error);
                const auto back_lines = splitSignMessage(back_message, &error);
                if (!back_lines)
                    throw std::runtime_error("back sign text readback failed: " + error);
                snapshot.front.lines = *front_lines;
                snapshot.back.lines = *back_lines;
                snapshot.actor_status = SignActorStatus::ExperimentalTextCaptured;
            }
            snapshot.canonical_snbt.clear();
            snapshot.revision = calculateSignRevision(snapshot);
            return snapshot;
        } catch (...) {
            return std::nullopt;
        }
    }

    SignApplyResult apply(const SignPatch &patch, const bool force) override {
        if (!exact_runtime_)
            return runtimeMismatch();
        if (!text_bridge_.executableIdentityMatch())
            return binaryIdentityMismatch();
        if (!server_.isPrimaryThread()) {
            return {
                SignApplyStatus::AdapterError,
                "live sign apply must run on the primary thread",
                0,
            };
        }

        auto current = capture(patch.location);
        if (!current)
            return {SignApplyStatus::NotASign, "sign not found", 0};
        if (force) {
            return {
                SignApplyStatus::Unsupported,
                "force mutation is disabled in the experimental live adapter",
                current->revision,
            };
        }
        if (patch.expected_revision && *patch.expected_revision != current->revision) {
            return {
                SignApplyStatus::Conflict,
                "sign revision changed",
                current->revision,
            };
        }
        if (requiresSignNbt(patch))
            return nbtUnsupported(current->revision);
        if (!patch.send_client_update) {
            return {
                SignApplyStatus::Unsupported,
                "the Endstone public block write always sends a client update",
                current->revision,
            };
        }
        if (!patch.persist) {
            return {
                SignApplyStatus::Unsupported,
                "non-persistent live sign writes are not available",
                current->revision,
            };
        }
        if (requestsStructuralChange(patch)) {
            return {
                SignApplyStatus::Unsupported,
                "structural sign replacement is disabled until NBT-safe rollback and "
                "hosted postcondition evidence are available",
                current->revision,
            };
        }

        if (requestsPlainText(patch)) {
            if (!text_bridge_.ready())
                return textGateClosed(text_bridge_, current->revision);
            if (requestsStructuralChange(patch)) {
                return {
                    SignApplyStatus::Unsupported,
                    "structural block changes cannot be combined with an experimental "
                    "plain-text write",
                    current->revision,
                };
            }

            auto native =
                locateNativeSignActor(server_, patch.location, &text_bridge_);
            if (!native.access) {
                return {
                    native.status == SignActorStatus::ChunkUnavailable
                        ? SignApplyStatus::ChunkUnavailable
                        : SignApplyStatus::NotASign,
                    "the target block has no compatible native sign actor",
                    current->revision,
                };
            }
            try {
                const auto safe_representation =
                    [this, &native](const SignSide side) {
                        return text_bridge_.plainMessage(
                                   *native.access->actor, side) &&
                               text_bridge_.filteredMessageEmpty(
                                   *native.access->actor, side);
                    };
                if ((patch.front && !safe_representation(SignSide::Front)) ||
                    (patch.back && !safe_representation(SignSide::Back))) {
                    return {
                        SignApplyStatus::Unsupported,
                        "experimental plain-text writes do not replace an existing "
                        "TextObject or leave stale filtered text; use a disposable sign "
                        "containing normal unfiltered text",
                        current->revision,
                    };
                }
            } catch (const std::exception &error) {
                return {
                    SignApplyStatus::AdapterError,
                    std::string("could not inspect exact sign text representation: ") +
                        error.what(),
                    current->revision,
                };
            }

            struct TextMutation {
                SignSide side{SignSide::Front};
                std::string before_message;
                std::string before_owner;
                std::string after_message;
                bool changed{};
            };
            std::vector<TextMutation> mutations;
            mutations.reserve(2);
            try {
                const auto append =
                    [this, &mutations, &native](const SignSide side,
                                               const SignText &before,
                                               const SignTextPatch &requested) {
                        const auto after = applyTextPatch(before, requested);
                        auto before_message =
                            text_bridge_.rawMessage(*native.access->actor, side);
                        const bool changed = after.lines != before.lines;
                        mutations.push_back({
                            side,
                            before_message,
                            text_bridge_.ownerXuid(*native.access->actor, side),
                            changed ? flattenSignLines(after.lines)
                                    : std::move(before_message),
                            changed,
                        });
                    };
                if (patch.front)
                    append(SignSide::Front, current->front, *patch.front);
                if (patch.back)
                    append(SignSide::Back, current->back, *patch.back);
            } catch (const std::exception &error) {
                return {
                    SignApplyStatus::AdapterError,
                    std::string("could not prepare exact sign text write: ") + error.what(),
                    current->revision,
                };
            }
            if (std::ranges::any_of(
                    mutations, [](const TextMutation &mutation) {
                        return mutation.changed &&
                               (mutation.before_message.size() >
                                   ExperimentalLinuxTextBridge::
                                       SafeTransferredMessageBytes ||
                               mutation.after_message.size() >
                                   ExperimentalLinuxTextBridge::
                                       SafeTransferredMessageBytes ||
                               mutation.before_owner.size() >
                                   ExperimentalLinuxTextBridge::
                                       SafeTransferredMessageBytes);
                    })) {
                return {
                    SignApplyStatus::Unsupported,
                    "this first exact Linux text probe requires the old message, new "
                    "message, and preserved owner XUID to fit 22 UTF-8 bytes each "
                    "(message size includes three line separators); no mutation was "
                    "attempted",
                    current->revision,
                };
            }

            const auto rollback = [this, &mutations, &patch]() noexcept {
                try {
                    auto rollback_actor = locateNativeSignActor(
                        server_, patch.location, &text_bridge_);
                    if (!rollback_actor.access)
                        return false;
                    for (const auto &mutation : mutations) {
                        if (mutation.changed) {
                            text_bridge_.setMessage(*rollback_actor.access->actor,
                                                    mutation.side,
                                                    mutation.before_message,
                                                    mutation.before_owner);
                        }
                    }
                    signalActorChanged(*rollback_actor.access);
                    auto verified_actor = locateNativeSignActor(
                        server_, patch.location, &text_bridge_);
                    if (!verified_actor.access)
                        return false;
                    return std::ranges::all_of(
                        mutations, [this, &verified_actor](
                                       const TextMutation &mutation) {
                            return text_bridge_.rawMessage(
                                       *verified_actor.access->actor,
                                       mutation.side) ==
                                       mutation.before_message &&
                                   text_bridge_.ownerXuid(
                                       *verified_actor.access->actor,
                                       mutation.side) ==
                                       mutation.before_owner &&
                                   text_bridge_.plainMessage(
                                       *verified_actor.access->actor,
                                       mutation.side) &&
                                   text_bridge_.filteredMessageEmpty(
                                       *verified_actor.access->actor,
                                       mutation.side);
                        });
                } catch (...) {
                    return false;
                }
            };

            try {
                const bool changed = std::ranges::any_of(
                    mutations, [](const TextMutation &mutation) {
                        return mutation.changed;
                    });
                if (!changed) {
                    return {
                        SignApplyStatus::Applied,
                        "plain sign text unchanged",
                        current->revision,
                    };
                }
                for (const auto &mutation : mutations) {
                    if (mutation.changed) {
                        text_bridge_.setMessage(*native.access->actor, mutation.side,
                                                mutation.after_message,
                                                mutation.before_owner);
                    }
                }
                signalActorChanged(*native.access);

                const auto readback_actor = locateNativeSignActor(
                    server_, patch.location, &text_bridge_);
                const bool readback_matches =
                    readback_actor.access &&
                    std::ranges::all_of(
                        mutations, [this, &readback_actor](
                                       const TextMutation &mutation) {
                            return text_bridge_.rawMessage(
                                       *readback_actor.access->actor,
                                       mutation.side) ==
                                       mutation.after_message &&
                                   text_bridge_.ownerXuid(
                                       *readback_actor.access->actor,
                                       mutation.side) ==
                                       mutation.before_owner &&
                                   text_bridge_.plainMessage(
                                       *readback_actor.access->actor,
                                       mutation.side) &&
                                   text_bridge_.filteredMessageEmpty(
                                       *readback_actor.access->actor,
                                       mutation.side);
                        });
                auto updated = readback_matches ? capture(patch.location) : std::nullopt;
                if (!readback_matches || !updated ||
                    updated->actor_status !=
                        SignActorStatus::ExperimentalTextCaptured) {
                    if (!rollback()) {
                        return {
                            SignApplyStatus::RollbackFailed,
                            "exact sign text readback failed and the original text could "
                            "not be verified after rollback",
                            current->revision,
                        };
                    }
                    return {
                        SignApplyStatus::AdapterError,
                        "exact sign text readback failed; original text was restored",
                        current->revision,
                    };
                }
                return {
                    SignApplyStatus::Applied,
                    "applied exact-hash-gated Linux plain sign text with readback",
                    updated->revision,
                };
            } catch (const std::exception &error) {
                if (!rollback()) {
                    return {
                        SignApplyStatus::RollbackFailed,
                        std::string("plain sign text write failed and rollback could not be "
                                    "verified: ") + error.what(),
                        current->revision,
                    };
                }
                return {
                    SignApplyStatus::AdapterError,
                    std::string("plain sign text write failed; original text was restored: ") +
                        error.what(),
                    current->revision,
                };
            }
        }

        if (!patch.block_identifier && patch.state_updates.empty() &&
            patch.state_removals.empty()) {
            return {
                SignApplyStatus::Applied,
                "structural sign data unchanged",
                current->revision,
            };
        }

        auto identifier = patch.block_identifier.value_or(current->block_identifier);
        auto states = current->states;
        for (const auto &[key, value] : patch.state_updates) {
            states.insert_or_assign(key, value);
        }
        for (const auto &key : patch.state_removals)
            states.erase(key);
        if (const auto error = validateSignBlockStates(identifier, states)) {
            return {
                SignApplyStatus::InvalidPatch,
                *error,
                current->revision,
            };
        }

        try {
            auto access = locatePublicBlock(server_, patch.location);
            if (!access) {
                return {
                    SignApplyStatus::ChunkUnavailable,
                    "dimension, chunk, or block unavailable",
                    current->revision,
                };
            }
            auto replacement = createRegisteredBlockData(server_, identifier, states);
            if (!replacement.type_registered) {
                return {
                    SignApplyStatus::InvalidPatch,
                    "block type is absent from the Endstone block registry",
                    current->revision,
                };
            }
            if (!replacement.data) {
                return {
                    SignApplyStatus::InvalidPatch,
                    "Endstone rejected the requested sign block data",
                    current->revision,
                };
            }

            access->block->setData(*replacement.data, false);
            auto native =
                locateNativeSignActor(server_, patch.location, &text_bridge_);
            if (native.access)
                signalActorChanged(*native.access);

            auto updated = capture(patch.location);
            if (!updated) {
                return {
                    SignApplyStatus::AdapterError,
                    "structural sign write completed but readback did not find a sign "
                    "actor",
                    0,
                };
            }
            return {
                SignApplyStatus::Applied,
                "applied sign identifier/states through the Endstone v0.11.6 block "
                "boundary",
                updated->revision,
            };
        } catch (const std::invalid_argument &error) {
            return {
                SignApplyStatus::InvalidPatch,
                error.what(),
                current->revision,
            };
        } catch (const std::exception &error) {
            return {
                SignApplyStatus::AdapterError,
                error.what(),
                current->revision,
            };
        }
    }

    SignApplyResult place(const SignPlaceRequest &request, const bool force) override {
        if (!exact_runtime_)
            return runtimeMismatch();
        if (!text_bridge_.executableIdentityMatch())
            return binaryIdentityMismatch();
        if (!server_.isPrimaryThread()) {
            return {
                SignApplyStatus::AdapterError,
                "live sign placement must run on the primary thread",
                0,
            };
        }
        if (requiresSignNbt(request))
            return nbtUnsupported(0);
        if (!request.send_client_update) {
            return {
                SignApplyStatus::Unsupported,
                "the Endstone public block write always sends a client update",
                0,
            };
        }
        if (!request.persist) {
            return {
                SignApplyStatus::Unsupported,
                "non-persistent sign placement is not available",
                0,
            };
        }
        if (force || request.replace_policy == SignReplacePolicy::Force) {
            return {
                SignApplyStatus::Unsupported,
                "the experimental live adapter permits blank placement into air only; "
                "force placement is disabled",
                0,
            };
        }
        if (const auto error = validateSignBlockStates(request.block_identifier, request.states)) {
            return {SignApplyStatus::InvalidPatch, *error, 0};
        }

        try {
            auto access = locatePublicBlock(server_, request.location);
            if (!access) {
                return {
                    SignApplyStatus::ChunkUnavailable,
                    "dimension, chunk, or block unavailable",
                    0,
                };
            }
            const auto before_sign = capture(request.location);
            const auto before_revision = before_sign ? before_sign->revision : 0;
            if (request.expected_destination_revision && !force &&
                *request.expected_destination_revision != before_revision) {
                return {
                    SignApplyStatus::Conflict,
                    "destination revision changed",
                    before_revision,
                };
            }

            const bool is_air = access->data->getType() == "minecraft:air";
            const bool replaces = request.replace_policy == SignReplacePolicy::Force;
            if (!is_air && !replaces) {
                const auto message =
                    request.replace_policy == SignReplacePolicy::ReplaceableOnly
                        ? "destination is not air; this adapter cannot prove that a "
                          "non-air block is replaceable"
                        : "destination block is not air";
                return {SignApplyStatus::BlockOccupied, message, before_revision};
            }

            auto replacement = createRegisteredBlockData(
                server_, request.block_identifier, request.states);
            if (!replacement.type_registered) {
                return {
                    SignApplyStatus::InvalidPatch,
                    "block type is absent from the Endstone block registry",
                    before_revision,
                };
            }
            if (!replacement.data) {
                return {
                    SignApplyStatus::InvalidPatch,
                    "Endstone rejected the requested sign block data",
                    before_revision,
                };
            }
            access->block->setData(*replacement.data, false);

            const auto rollback = [&access]() noexcept {
                try {
                    access->block->setData(*access->data, false);
                    auto restored = access->block->getData();
                    return restored && restored->getType() == access->data->getType() &&
                           fromEndstoneStates(restored->getBlockStates()) ==
                               fromEndstoneStates(access->data->getBlockStates());
                } catch (...) {
                    return false;
                }
            };
            const auto fail_after_write =
                [&rollback, before_revision](std::string message) {
                    if (!rollback()) {
                        return SignApplyResult{
                            SignApplyStatus::RollbackFailed,
                            std::move(message) +
                                "; original block data could not be restored and verified",
                            before_revision,
                        };
                    }
                    return SignApplyResult{
                        SignApplyStatus::AdapterError,
                        std::move(message) +
                            "; original block data was restored and verified",
                        before_revision,
                    };
                };

            try {
                auto native =
                    locateNativeSignActor(server_, request.location, &text_bridge_);
                if (!native.access) {
                    return fail_after_write(
                        "sign block was placed but its vanilla sign actor was not "
                        "available");
                }
                signalActorChanged(*native.access);
                auto updated = capture(request.location);
                if (!updated) {
                    return fail_after_write(
                        "sign block was placed but structural readback failed");
                }
                const bool states_match = std::ranges::all_of(
                    request.states, [&updated](const auto &entry) {
                        const auto actual = updated->states.find(entry.first);
                        return actual != updated->states.end() &&
                               actual->second == entry.second;
                    });
                if (updated->block_identifier != request.block_identifier ||
                    !states_match) {
                    return fail_after_write(
                        "sign block was placed but identifier/state readback did not "
                        "match the request");
                }
                return {
                    SignApplyStatus::Applied,
                    "placed a blank sign through the Endstone v0.11.6 block boundary",
                    updated->revision,
                };
            } catch (const std::exception &error) {
                return fail_after_write(
                    std::string("sign placement failed after the block write: ") +
                    error.what());
            } catch (...) {
                return fail_after_write(
                    "sign placement failed after the block write with an unknown error");
            }
        } catch (const std::invalid_argument &error) {
            return {SignApplyStatus::InvalidPatch, error.what(), 0};
        } catch (const std::exception &error) {
            return {SignApplyStatus::AdapterError, error.what(), 0};
        }
    }

    SignApplyResult remove(const SignRemoveRequest &request, const bool force) override {
        if (!exact_runtime_)
            return runtimeMismatch();
        if (!text_bridge_.executableIdentityMatch())
            return binaryIdentityMismatch();
        if (!server_.isPrimaryThread()) {
            return {
                SignApplyStatus::AdapterError,
                "live sign removal must run on the primary thread",
                0,
            };
        }
        auto current = capture(request.location);
        if (!current)
            return {SignApplyStatus::NotASign, "sign not found", 0};
        if (force || !request.expected_revision || *request.expected_revision == 0) {
            return {
                SignApplyStatus::Unsupported,
                "experimental removal requires a nonzero expected revision and force=false",
                current->revision,
            };
        }
        if (*request.expected_revision != current->revision) {
            return {
                SignApplyStatus::Conflict,
                "sign revision changed",
                current->revision,
            };
        }
        if (request.drop_item) {
            return {
                SignApplyStatus::Unsupported,
                "verified sign-item drop semantics are not available in the "
                "experimental adapter",
                current->revision,
            };
        }
        if (!request.send_client_update) {
            return {
                SignApplyStatus::Unsupported,
                "the Endstone public block write always sends a client update",
                current->revision,
            };
        }

        try {
            auto access = locatePublicBlock(server_, request.location);
            if (!access) {
                return {
                    SignApplyStatus::ChunkUnavailable,
                    "dimension, chunk, or block unavailable",
                    current->revision,
                };
            }
            access->block->setType("minecraft:air", false);
            auto readback = locatePublicBlock(server_, request.location);
            if (!readback || readback->data->getType() != "minecraft:air") {
                return {
                    SignApplyStatus::AdapterError,
                    "sign removal did not read back as air",
                    current->revision,
                };
            }
            return {
                SignApplyStatus::Applied,
                "removed sign without an item drop",
                0,
            };
        } catch (const std::exception &error) {
            return {
                SignApplyStatus::AdapterError,
                error.what(),
                current->revision,
            };
        }
    }

    SignTransactionResult transact(const SignTransaction &transaction) override {
        if (transaction.operations.empty()) {
            return {
                SignApplyStatus::Applied,
                "empty transaction",
                {},
                false,
            };
        }
        if (transaction.operations.size() != 1) {
            return {
                SignApplyStatus::Unsupported,
                "the experimental structural adapter does not claim atomic "
                "multi-operation transactions",
                {},
                false,
            };
        }

        auto operation_result = std::visit(
            [this, &transaction](const auto &operation) {
                using T = std::decay_t<decltype(operation)>;
                if constexpr (std::is_same_v<T, SignPlaceRequest>) {
                    return place(operation, transaction.force);
                } else if constexpr (std::is_same_v<T, SignPatch>) {
                    return apply(operation, transaction.force);
                } else {
                    return remove(operation, transaction.force);
                }
            },
            transaction.operations.front());
        return {
            operation_result.status,
            operation_result.message,
            {operation_result},
            false,
        };
    }

    SignApplyResult openEditor(endstone::Player &player,
                               const SignOpenEditorRequest &request) override {
        if (!exact_runtime_)
            return runtimeMismatch();
        if (!text_bridge_.executableIdentityMatch())
            return binaryIdentityMismatch();
        if (!server_.isPrimaryThread()) {
            return {
                SignApplyStatus::AdapterError,
                "opening a native sign editor must run on the primary thread",
                0,
            };
        }
        auto current = capture(request.location);
        if (!current)
            return {SignApplyStatus::NotASign, "sign not found", 0};
        if (request.expected_revision && *request.expected_revision != current->revision) {
            return {
                SignApplyStatus::Conflict,
                "sign revision changed",
                current->revision,
            };
        }
        if (request.acquire_lock) {
            return {
                SignApplyStatus::Unsupported,
                "Player::openSign is available, but the SignBlockActor editor-lock "
                "setter is not verified; retry with acquire_lock=false for the UI "
                "probe",
                current->revision,
            };
        }
        if (!request.bypass_wax) {
            return {
                SignApplyStatus::Unsupported,
                "the experimental structural capture cannot read IsWaxed; retry "
                "with bypass_wax=true only in the disposable test world",
                current->revision,
            };
        }
        if (player.getDimension().getName() != request.location.dimension) {
            return {
                SignApplyStatus::PermissionDenied,
                "player and sign must be in the same dimension",
                current->revision,
            };
        }
        const auto native_actor =
            locateNativeSignActor(server_, request.location, &text_bridge_);
        if (!native_actor.access) {
            return {
                SignApplyStatus::NotASign,
                "the target block has no compatible vanilla sign actor",
                current->revision,
            };
        }

        try {
            auto &native_player = static_cast<endstone::core::EndstonePlayer &>(player).getHandle();
            const ::BlockPos position(request.location.x, request.location.y, request.location.z);
            native_player.openSign(position, request.side == SignSide::Front);
            return {
                SignApplyStatus::Applied,
                "sent the pinned Player::openSign UI request without claiming an "
                "editor lock",
                current->revision,
            };
        } catch (const std::exception &error) {
            return {
                SignApplyStatus::AdapterError,
                error.what(),
                current->revision,
            };
        }
    }

  private:
    endstone::Server &server_;
    bool exact_runtime_{};
    ExperimentalLinuxTextBridge text_bridge_;
};

} // namespace

std::shared_ptr<ISignAdapter> makeExperimentalBds2630SignAdapter(endstone::Server &server) {
    return std::make_shared<ExperimentalBds2630SignAdapter>(server);
}

} // namespace endstone_sign
