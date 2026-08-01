#include "endstone_sign/experimental_bds_26_30_adapter.h"

#include "endstone_sign/events.h"
#include "endstone_sign/generated/native_manifest_data.h"
#include "endstone_sign/internal/experimental_runtime_identity.h"
#include "endstone_sign/native_binary_identity.h"
#include "endstone_sign/placement.h"
#include "endstone_sign/schema.h"

#include <endstone/endstone.hpp>
#include <funchook.h>

#include "bedrock/world/actor/player/player.h"
#include "bedrock/world/level/block/actor/block_actor.h"
#include "bedrock/world/level/block/actor/vanilla_block_actor.h"
#include "bedrock/world/level/block_source.h"
#include "bedrock/deps/json/value.h"
#include "bedrock/nbt/compound_tag.h"
#include "endstone/block/block_type.h"
#include "endstone/core/level/dimension.h"
#include "endstone/core/player.h"
#include <nlohmann/json.hpp>

#include <algorithm>
#include <array>
#include <cctype>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cmath>
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

#ifndef ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
#define ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION 0
#endif

#ifndef ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE
#define ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE 0
#endif

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

#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
    [[nodiscard]] SignText captureText(const BlockActor &actor,
                                       const SignSide side) const {
        requireCompatible(actor);
        const auto *text = sideText(actor, side);
        SignText result;
        std::string error;
        const auto lines = splitSignMessage(rawMessage(actor, side), &error);
        if (!lines)
            throw std::runtime_error("native sign message is invalid: " + error);
        result.lines = *lines;
        result.filtered_message = nativeString(text, FilteredMessageOffset, 16 * 1024,
                                               "filtered sign message");
        result.message_is_text_object = !plainMessage(actor, side);
        result.text_object = result.message_is_text_object
                                 ? serializeTextObject(text)
                                 : std::string{};
        result.argb = colorToArgb(text + TextColorOffset);
        result.glowing = byteAt(text, GlowingOffset) != 0;
        result.hide_glow_outline = byteAt(text, HideGlowOutlineOffset) != 0;
        result.persist_formatting = byteAt(text, PersistFormattingOffset) != 0;
        result.owner_xuid = nativeString(text, OwnerOffset, 128, "sign text owner");
        return result;
    }

    void applyText(BlockActor &actor, const SignSide side,
                   const SignText &value) const {
        requireCompatible(actor);
        const auto text_value = value.message_is_text_object
                                    ? canonicalTextObject(value.text_object)
                                    : flattenSignLines(value.lines);
        CompoundTag tag;
        tag.putBoolean("IgnoreLighting", value.glowing);
        tag.putBoolean("HideGlowOutline", value.hide_glow_outline);
        tag.putInt("SignTextColor", static_cast<std::int32_t>(value.argb));
        tag.putBoolean("PersistFormatting", value.persist_formatting);
        tag.putString("TextOwner", value.owner_xuid);
        tag.putString("Text", text_value);
        tag.putString("FilteredText", value.filtered_message);
        text_load_(sideText(actor, side), &tag, TextLoadModeAllData);
    }

    void applyClientPayload(BlockActor &actor, const CompoundTag &payload) const {
        requireCompatible(actor);
        if (const auto *front = payload.getCompound("FrontText"))
            text_load_(sideText(actor, SignSide::Front), front, TextLoadModeNetwork);
        if (const auto *back = payload.getCompound("BackText"))
            text_load_(sideText(actor, SignSide::Back), back, TextLoadModeNetwork);
    }

    void setOwnerXuid(BlockActor &actor, const SignSide side,
                      std::string owner_xuid) const {
        requireCompatible(actor);
        if (owner_xuid.size() > 128 || owner_xuid.find('\0') != std::string::npos ||
            !isValidUtf8(owner_xuid)) {
            throw std::invalid_argument("native sign text owner failed validation");
        }
        auto *text = reinterpret_cast<std::byte *>(sideText(actor, side));
        *reinterpret_cast<std::string *>(text + OwnerOffset) =
            std::move(owner_xuid);
    }

    [[nodiscard]] bool waxed(const BlockActor &actor) const {
        requireCompatible(actor);
        return byteAt(reinterpret_cast<const std::byte *>(&actor), WaxedOffset) != 0;
    }

    void setWaxed(BlockActor &actor, const bool value) const {
        requireCompatible(actor);
        set_waxed_(&actor, value);
    }

    [[nodiscard]] std::int64_t lockedForEditingBy(const BlockActor &actor) const {
        requireCompatible(actor);
        std::int64_t value{};
        std::memcpy(&value, reinterpret_cast<const std::byte *>(&actor) + LockOffset,
                    sizeof(value));
        return value;
    }

    void setLockedForEditingBy(BlockActor &actor, const std::int64_t value) const {
        requireCompatible(actor);
        std::memcpy(reinterpret_cast<std::byte *>(&actor) + LockOffset, &value,
                    sizeof(value));
    }

    [[nodiscard]] bool remoteProfanityFilter(const BlockActor &actor) const {
        requireCompatible(actor);
        return byteAt(reinterpret_cast<const std::byte *>(&actor),
                      RemoteProfanityFilterOffset) != 0;
    }

    [[nodiscard]] bool localProfanityFilter(const BlockActor &actor) const {
        requireCompatible(actor);
        return byteAt(reinterpret_cast<const std::byte *>(&actor),
                      LocalProfanityFilterOffset) != 0;
    }

    void setProfanityFilters(BlockActor &actor, const bool remote,
                             const bool local) const {
        requireCompatible(actor);
        auto *bytes = reinterpret_cast<std::byte *>(&actor);
        bytes[RemoteProfanityFilterOffset] = static_cast<std::byte>(remote);
        bytes[LocalProfanityFilterOffset] = static_cast<std::byte>(local);
    }

    [[nodiscard]] std::uintptr_t updateTextFromClientAddress() const {
#if defined(__linux__) && defined(__x86_64__)
        requireReady();
        return image_base_ + UpdateTextFromClientRva;
#else
        throw std::runtime_error(
            "player-edit hook address is available only on Linux x64");
#endif
    }
#endif

  private:
    using GetRawMessage = const std::string &(*)(const BlockActor *, std::int32_t);
    using IsStringMessage = bool (*)(const BlockActor *, std::int32_t);
    using SetMessage =
        void (*)(BlockActor *, std::int32_t, std::string, std::string);
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
    using TextLoad = void (*)(void *, const CompoundTag *, std::int32_t);
    using TextObjectJson = Json::Value (*)(const void *);
    using SetWaxed = void (*)(BlockActor *, bool);
#endif

    static constexpr std::uintptr_t SignBlockActorVtableRva = 0x0DCF6BA8;
    static constexpr std::uintptr_t HangingSignBlockActorVtableRva = 0x0DCFC968;

#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
    static constexpr std::size_t FilteredMessageOffset = 0x18;
    static constexpr std::size_t TextColorOffset = 0x108;
    static constexpr std::size_t GlowingOffset = 0x118;
    static constexpr std::size_t HideGlowOutlineOffset = 0x119;
    static constexpr std::size_t PersistFormattingOffset = 0x11A;
    static constexpr std::size_t OwnerOffset = 0x120;
    static constexpr std::size_t TextObjectRootOffset = 0x30;
    static constexpr std::size_t WaxedOffset = 0xD8;
    static constexpr std::size_t LockOffset = 0xE0;
    static constexpr std::size_t RemoteProfanityFilterOffset = 0x190;
    static constexpr std::size_t LocalProfanityFilterOffset = 0x191;
    static constexpr std::int32_t TextLoadModeNetwork = 0;
    static constexpr std::int32_t TextLoadModeAllData = 1;
#endif

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
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
    static constexpr std::uintptr_t TextLoadRva = 0x0BE0E390;
    static constexpr std::size_t TextLoadSize = 4586;
    static constexpr std::string_view TextLoadSha256 =
        "934bc7322f7beaca4d01a8073e7eef47d7e13ba243674f5ac3760d5315f7cfc7";
    static constexpr std::uintptr_t TextObjectJsonRva = 0x09DD50D0;
    static constexpr std::size_t TextObjectJsonSize = 122;
    static constexpr std::string_view TextObjectJsonSha256 =
        "9b385769e1291cf163e38eea2a0ed7f8527894af81f3201cff2889262486b58a";
    static constexpr std::uintptr_t SetWaxedRva = 0x0BE10C80;
    static constexpr std::size_t SetWaxedSize = 12;
    static constexpr std::string_view SetWaxedSha256 =
        "dfee51213b116264be00582eda841923fcff93888b1ac4aab51acfb32f2cc6f5";
    static constexpr std::uintptr_t UpdateTextFromClientRva = 0x0BE0F580;
    static constexpr std::size_t UpdateTextFromClientSize = 1825;
    static constexpr std::string_view UpdateTextFromClientSha256 =
        "1c952de008bdaa2db728369954e0cdbb5e8653005650e2ea18ac74f04ebea97d";
#endif

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
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        const auto text_load_address = base + TextLoadRva;
        const auto text_object_json_address = base + TextObjectJsonRva;
        const auto set_waxed_address = base + SetWaxedRva;
        const auto update_text_address = base + UpdateTextFromClientRva;
        bool contains_text_load = false;
        bool contains_text_object_json = false;
        bool contains_set_waxed = false;
        bool contains_update_text = false;
#endif
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
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
            contains_text_load = contains_text_load ||
                                 segmentContains(segment_begin, header.p_memsz,
                                                 text_load_address, TextLoadSize);
            contains_text_object_json = contains_text_object_json ||
                                        segmentContains(segment_begin, header.p_memsz,
                                                        text_object_json_address,
                                                        TextObjectJsonSize);
            contains_set_waxed = contains_set_waxed ||
                                 segmentContains(segment_begin, header.p_memsz,
                                                 set_waxed_address, SetWaxedSize);
            contains_update_text = contains_update_text ||
                                   segmentContains(segment_begin, header.p_memsz,
                                                   update_text_address,
                                                   UpdateTextFromClientSize);
#endif
        }
        if (!contains_set || !contains_get || !contains_string_message
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
            || !contains_text_load || !contains_text_object_json ||
               !contains_set_waxed || !contains_update_text
#endif
        )
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
                                 IsStringMessageSha256)
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
            || !functionHashMatches(*image.base + TextLoadRva, TextLoadSize,
                                    TextLoadSha256) ||
            !functionHashMatches(*image.base + TextObjectJsonRva,
                                 TextObjectJsonSize, TextObjectJsonSha256) ||
            !functionHashMatches(*image.base + SetWaxedRva, SetWaxedSize,
                                 SetWaxedSha256) ||
            !functionHashMatches(*image.base + UpdateTextFromClientRva,
                                 UpdateTextFromClientSize,
                                 UpdateTextFromClientSha256)
#endif
        ) {
            failure_ = "exact Sign text function fingerprint mismatch";
            return;
        }

        set_message_ = reinterpret_cast<SetMessage>(set_address);
        get_raw_message_ = reinterpret_cast<GetRawMessage>(get_address);
        is_string_message_ =
            reinterpret_cast<IsStringMessage>(string_message_address);
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        text_load_ = reinterpret_cast<TextLoad>(*image.base + TextLoadRva);
        text_object_json_ =
            reinterpret_cast<TextObjectJson>(*image.base + TextObjectJsonRva);
        set_waxed_ = reinterpret_cast<SetWaxed>(*image.base + SetWaxedRva);
#endif
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

#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
    [[nodiscard]] static std::uint8_t byteAt(const std::byte *base,
                                             const std::size_t offset) noexcept {
        return std::to_integer<std::uint8_t>(base[offset]);
    }

    [[nodiscard]] static std::string nativeString(
        const std::byte *base, const std::size_t offset,
        const std::size_t maximum, const std::string_view label) {
        const auto &value = *reinterpret_cast<const std::string *>(base + offset);
        if (value.size() > maximum || value.find('\0') != std::string::npos ||
            !isValidUtf8(value)) {
            throw std::runtime_error(std::string(label) + " failed validation");
        }
        return value;
    }

    [[nodiscard]] static std::uint32_t colorToArgb(const std::byte *value) noexcept {
        std::array<float, 4> channels{};
        std::memcpy(channels.data(), value, sizeof(channels));
        const auto component = [](const float entry) {
            return static_cast<std::uint32_t>(std::lround(
                std::clamp(entry, 0.0F, 1.0F) * 255.0F));
        };
        return (component(channels[3]) << 24U) |
               (component(channels[0]) << 16U) |
               (component(channels[1]) << 8U) | component(channels[2]);
    }

    [[nodiscard]] static nlohmann::json jsonValue(const Json::Value &value) {
        switch (value.type()) {
        case Json::nullValue:
            return nullptr;
        case Json::intValue:
            return value.asInt64();
        case Json::uintValue:
            return value.asUInt64();
        case Json::realValue:
            return value.asDouble();
        case Json::stringValue:
            return value.asString();
        case Json::booleanValue:
            return value.asBool();
        case Json::arrayValue: {
            auto result = nlohmann::json::array();
            for (Json::ArrayIndex index = 0; index < value.size(); ++index)
                result.push_back(jsonValue(value[index]));
            return result;
        }
        case Json::objectValue: {
            auto result = nlohmann::json::object();
            for (const auto &name : value.getMemberNames())
                result[name] = jsonValue(value[name]);
            return result;
        }
        }
        throw std::runtime_error("native text object returned an unknown JSON type");
    }

    [[nodiscard]] static std::string canonicalTextObject(
        const std::string_view value) {
        nlohmann::json parsed;
        try {
            parsed = nlohmann::json::parse(value);
        } catch (const nlohmann::json::exception &error) {
            throw std::invalid_argument(
                std::string("text object is not valid JSON: ") + error.what());
        }
        if (!parsed.is_object()) {
            throw std::invalid_argument(
                "text object must contain a non-empty Bedrock rawtext array");
        }
        const auto rawtext = parsed.find("rawtext");
        if (rawtext == parsed.end() ||
            !rawtext->is_array() || rawtext->empty()) {
            throw std::invalid_argument(
                "text object must contain a non-empty Bedrock rawtext array");
        }
        return parsed.dump();
    }

    [[nodiscard]] std::string serializeTextObject(const std::byte *text) const {
        if (!text_object_json_)
            throw std::runtime_error("native text object serializer is unavailable");
        const auto value = text_object_json_(text + TextObjectRootOffset);
        const auto serialized = jsonValue(value).dump();
        if (serialized.size() > 64 * 1024 || !isValidUtf8(serialized))
            throw std::runtime_error("native sign text object failed validation");
        return serialized;
    }
#endif

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

#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
    [[nodiscard]] void *sideText(BlockActor &actor, const SignSide side) const {
        return const_cast<std::byte *>(
            sideText(static_cast<const BlockActor &>(actor), side));
    }
#endif

    GetRawMessage get_raw_message_{};
    IsStringMessage is_string_message_{};
    SetMessage set_message_{};
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
    TextLoad text_load_{};
    TextObjectJson text_object_json_{};
    SetWaxed set_waxed_{};
#endif
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

SignSnapshot applyPatchToSnapshot(SignSnapshot snapshot, const SignPatch &patch) {
    if (patch.block_identifier)
        snapshot.block_identifier = *patch.block_identifier;
    for (const auto &[key, value] : patch.state_updates)
        snapshot.states.insert_or_assign(key, value);
    for (const auto &key : patch.state_removals)
        snapshot.states.erase(key);
    if (patch.front)
        snapshot.front = applyTextPatch(snapshot.front, *patch.front);
    if (patch.back)
        snapshot.back = applyTextPatch(snapshot.back, *patch.back);
    if (patch.waxed)
        snapshot.waxed = *patch.waxed;
    if (patch.locked_for_editing_by)
        snapshot.locked_for_editing_by = *patch.locked_for_editing_by;
    if (patch.locked_for_editing_xuid) {
        if (patch.locked_for_editing_xuid->empty())
            snapshot.locked_for_editing_xuid.reset();
        else
            snapshot.locked_for_editing_xuid = *patch.locked_for_editing_xuid;
    }
    if (patch.remote_profanity_filter_enabled)
        snapshot.remote_profanity_filter_enabled =
            *patch.remote_profanity_filter_enabled;
    if (patch.local_profanity_filter_enabled)
        snapshot.local_profanity_filter_enabled =
            *patch.local_profanity_filter_enabled;
    snapshot.kind = classifySign(snapshot.block_identifier, snapshot.states);
    snapshot.canonical_snbt.clear();
    snapshot.revision = calculateSignRevision(snapshot);
    return snapshot;
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

#if !ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
SignApplyResult nbtUnsupported(const std::uint64_t revision) {
    return {
        SignApplyStatus::Unsupported,
        "filtered/text-object/color/glow/outline/formatting/owner, wax, profanity, "
        "and editor-lock mutation remain behind the unverified SignBlockActor NBT "
        "boundary",
        revision,
    };
}
#endif

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
        : server_(server), exact_runtime_(exactRuntime(server)) {
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        installPlayerEditHook();
#endif
    }

    ~ExperimentalBds2630SignAdapter() override {
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        uninstallPlayerEditHook();
#endif
    }

    void bindEventBus(std::shared_ptr<SignEventBus> event_bus) override {
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        event_bus_ = std::move(event_bus);
#else
        (void)event_bus;
#endif
    }

    [[nodiscard]] std::string_view name() const noexcept override {
        if (!exact_runtime_)
            return "bds-1.26.33.1-experimental-runtime-mismatch";
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        if (text_bridge_.ready())
            return "bds-1.26.33.1-linux-release";
#endif
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
        result.place = structural_mutation_gate;
        result.remove = structural_mutation_gate;  // No item drop.
        result.replace = structural_mutation_gate;
        result.clone = structural_mutation_gate;
        result.move = structural_mutation_gate;
        result.atomic_transactions = structural_mutation_gate;
        result.open_editor = structural_mutation_gate; // UI dispatch only.
        result.api_edit_events = structural_mutation_gate;
        result.client_updates = structural_mutation_gate;
        result.exact_build_match = exact_runtime_;

#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        const bool complete_native_gate = exact_runtime_ && text_bridge_.ready();
        result.read_text = complete_native_gate;
        result.write_text = complete_native_gate;
        result.front_and_back = complete_native_gate;
        result.per_line_write = complete_native_gate;
        result.text_objects = complete_native_gate;
        result.filtered_text = complete_native_gate;
        result.owner_xuid = complete_native_gate;
        result.text_color = complete_native_gate;
        result.glowing = complete_native_gate;
        result.hide_glow_outline = complete_native_gate;
        result.persist_formatting = complete_native_gate;
        result.waxed = complete_native_gate;
        result.editor_lock = complete_native_gate;
        result.open_editor = complete_native_gate;
        result.player_edit_events = complete_native_gate && hook_installed_ &&
                                    !event_bus_.expired();
        result.restart_persistence = complete_native_gate;
        result.exact_binary_hash_match = complete_native_gate;
        result.symbols_validated = complete_native_gate;
        // Source control remains fail-closed. The activation workflow is the
        // only writer that can embed a reviewed disposable-world pass here.
        result.stage_probe_passed = complete_native_gate &&
                                    generated::DisposableWorldProbePassed;
        return result;
#else
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
#endif
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
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
                snapshot.front = text_bridge_.captureText(
                    *native.access->actor, SignSide::Front);
                snapshot.back = text_bridge_.captureText(
                    *native.access->actor, SignSide::Back);
                snapshot.waxed = text_bridge_.waxed(*native.access->actor);
                snapshot.locked_for_editing_by =
                    text_bridge_.lockedForEditingBy(*native.access->actor);
                if (snapshot.locked_for_editing_by >= 0) {
                    for (auto *online : server_.getOnlinePlayers()) {
                        if (!online) continue;
                        auto &handle = static_cast<endstone::core::EndstonePlayer &>(
                                           *online).getHandle();
                        if (handle.getOrCreateUniqueID().raw_id ==
                            snapshot.locked_for_editing_by) {
                            snapshot.locked_for_editing_xuid = online->getXuid();
                            break;
                        }
                    }
                }
                snapshot.remote_profanity_filter_enabled =
                    text_bridge_.remoteProfanityFilter(*native.access->actor);
                snapshot.local_profanity_filter_enabled =
                    text_bridge_.localProfanityFilter(*native.access->actor);
                snapshot.actor_status = SignActorStatus::Captured;
#else
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
#endif
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
#if !ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        if (force) {
            return {
                SignApplyStatus::Unsupported,
                "force mutation is disabled in the experimental live adapter",
                current->revision,
            };
        }
#endif
        if (!force && patch.expected_revision &&
            *patch.expected_revision != current->revision) {
            return {
                SignApplyStatus::Conflict,
                "sign revision changed",
                current->revision,
            };
        }
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        if (requestsStructuralChange(patch)) {
            if (!patch.send_client_update || !patch.persist) {
                return {
                    SignApplyStatus::Unsupported,
                    "the release adapter supports persistent mutations with client updates",
                    current->revision,
                };
            }

            auto expected = applyPatchToSnapshot(*current, patch);
            if (expected.locked_for_editing_xuid &&
                !patch.locked_for_editing_by) {
                bool matched = false;
                for (auto *online : server_.getOnlinePlayers()) {
                    if (!online ||
                        online->getXuid() != *expected.locked_for_editing_xuid)
                        continue;
                    auto &handle =
                        static_cast<endstone::core::EndstonePlayer &>(*online)
                            .getHandle();
                    expected.locked_for_editing_by =
                        handle.getOrCreateUniqueID().raw_id;
                    matched = true;
                    break;
                }
                if (!matched) {
                    return {
                        SignApplyStatus::InvalidPatch,
                        "locked_for_editing_xuid must identify an online player when no "
                        "native actor ID is supplied",
                        current->revision,
                    };
                }
            }
            if (const auto error = validateSignBlockStates(
                    expected.block_identifier, expected.states)) {
                return {SignApplyStatus::InvalidPatch, *error,
                        current->revision};
            }

            const auto write_snapshot = [this, &patch](
                                            const SignSnapshot &snapshot) {
                auto public_block = locatePublicBlock(server_, patch.location);
                if (!public_block)
                    throw std::runtime_error(
                        "dimension, chunk, or block unavailable");
                auto replacement = createRegisteredBlockData(
                    server_, snapshot.block_identifier, snapshot.states);
                if (!replacement.type_registered)
                    throw std::invalid_argument(
                        "block type is absent from the Endstone block registry");
                if (!replacement.data)
                    throw std::invalid_argument(
                        "Endstone rejected the requested sign block data");
                public_block->block->setData(*replacement.data, false);

                auto native = locateNativeSignActor(server_, patch.location,
                                                    &text_bridge_);
                if (!native.access)
                    throw std::runtime_error(
                        "replacement did not expose a compatible native sign actor");
                text_bridge_.applyText(*native.access->actor, SignSide::Front,
                                       snapshot.front);
                text_bridge_.applyText(*native.access->actor, SignSide::Back,
                                       snapshot.back);
                text_bridge_.setWaxed(*native.access->actor, snapshot.waxed);
                text_bridge_.setLockedForEditingBy(
                    *native.access->actor, snapshot.locked_for_editing_by);
                text_bridge_.setProfanityFilters(
                    *native.access->actor,
                    snapshot.remote_profanity_filter_enabled,
                    snapshot.local_profanity_filter_enabled);
                signalActorChanged(*native.access);
            };
            const auto rollback = [this, &write_snapshot, &current,
                                   &patch]() noexcept {
                try {
                    write_snapshot(*current);
                    const auto restored = capture(patch.location);
                    return restored && samePayload(*restored, *current);
                } catch (...) {
                    return false;
                }
            };

            try {
                write_snapshot(expected);
                const auto updated = capture(patch.location);
                if (updated && samePayload(*updated, expected)) {
                    return {
                        SignApplyStatus::Applied,
                        "atomically replaced the sign block data and complete native payload",
                        updated->revision,
                    };
                }
                if (!rollback()) {
                    return {
                        SignApplyStatus::RollbackFailed,
                        "combined structural/native readback failed and rollback could not be verified",
                        current->revision,
                    };
                }
                return {
                    SignApplyStatus::AdapterError,
                    "combined structural/native readback failed; original sign was restored",
                    current->revision,
                };
            } catch (const std::invalid_argument &error) {
                return {SignApplyStatus::InvalidPatch, error.what(),
                        current->revision};
            } catch (const std::exception &error) {
                if (!rollback()) {
                    return {
                        SignApplyStatus::RollbackFailed,
                        std::string("combined structural/native mutation and rollback failed: ") +
                            error.what(),
                        current->revision,
                    };
                }
                return {
                    SignApplyStatus::AdapterError,
                    std::string("combined structural/native mutation failed; original sign was restored: ") +
                        error.what(),
                    current->revision,
                };
            }
        }

        if (requestsPlainText(patch) || requiresSignNbt(patch)) {
            if (!patch.send_client_update || !patch.persist) {
                return {
                    SignApplyStatus::Unsupported,
                    "the release adapter supports persistent mutations with client updates",
                    current->revision,
                };
            }
            auto native = locateNativeSignActor(server_, patch.location, &text_bridge_);
            if (!native.access) {
                return {
                    native.status == SignActorStatus::ChunkUnavailable
                        ? SignApplyStatus::ChunkUnavailable
                        : SignApplyStatus::NotASign,
                    "the target block has no compatible native sign actor",
                    current->revision,
                };
            }

            auto expected = *current;
            if (patch.front)
                expected.front = applyTextPatch(expected.front, *patch.front);
            if (patch.back)
                expected.back = applyTextPatch(expected.back, *patch.back);
            if (patch.waxed) expected.waxed = *patch.waxed;
            if (patch.locked_for_editing_by)
                expected.locked_for_editing_by = *patch.locked_for_editing_by;
            if (patch.locked_for_editing_xuid) {
                if (patch.locked_for_editing_xuid->empty())
                    expected.locked_for_editing_xuid.reset();
                else
                    expected.locked_for_editing_xuid =
                        *patch.locked_for_editing_xuid;
            }
            if (patch.remote_profanity_filter_enabled)
                expected.remote_profanity_filter_enabled =
                    *patch.remote_profanity_filter_enabled;
            if (patch.local_profanity_filter_enabled)
                expected.local_profanity_filter_enabled =
                    *patch.local_profanity_filter_enabled;

            if (expected.locked_for_editing_xuid &&
                !patch.locked_for_editing_by) {
                bool matched = false;
                for (auto *online : server_.getOnlinePlayers()) {
                    if (!online || online->getXuid() != *expected.locked_for_editing_xuid)
                        continue;
                    auto &handle =
                        static_cast<endstone::core::EndstonePlayer &>(*online).getHandle();
                    expected.locked_for_editing_by =
                        handle.getOrCreateUniqueID().raw_id;
                    matched = true;
                    break;
                }
                if (!matched) {
                    return {
                        SignApplyStatus::InvalidPatch,
                        "locked_for_editing_xuid must identify an online player when no "
                        "native actor ID is supplied",
                        current->revision,
                    };
                }
            }

            const auto apply_snapshot = [this, &native](const SignSnapshot &snapshot) {
                text_bridge_.applyText(*native.access->actor, SignSide::Front,
                                       snapshot.front);
                text_bridge_.applyText(*native.access->actor, SignSide::Back,
                                       snapshot.back);
                text_bridge_.setWaxed(*native.access->actor, snapshot.waxed);
                text_bridge_.setLockedForEditingBy(
                    *native.access->actor, snapshot.locked_for_editing_by);
                text_bridge_.setProfanityFilters(
                    *native.access->actor,
                    snapshot.remote_profanity_filter_enabled,
                    snapshot.local_profanity_filter_enabled);
                signalActorChanged(*native.access);
            };
            try {
                apply_snapshot(expected);
                auto updated = capture(patch.location);
                if (updated && samePayload(*updated, expected)) {
                    return {
                        SignApplyStatus::Applied,
                        "applied and read back the complete native sign payload",
                        updated->revision,
                    };
                }
                apply_snapshot(*current);
                return {
                    SignApplyStatus::RollbackFailed,
                    "native sign readback differed from the request; rollback was attempted",
                    current->revision,
                };
            } catch (const std::exception &error) {
                try {
                    apply_snapshot(*current);
                } catch (...) {
                    return {
                        SignApplyStatus::RollbackFailed,
                        std::string("native sign mutation and rollback failed: ") + error.what(),
                        current->revision,
                    };
                }
                return {
                    SignApplyStatus::AdapterError,
                    std::string("native sign mutation failed and was rolled back: ") +
                        error.what(),
                    current->revision,
                };
            }
        }
#else
        if (requiresSignNbt(patch))
            return nbtUnsupported(current->revision);
#endif
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
#if !ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        if (requiresSignNbt(request))
            return nbtUnsupported(0);
#endif
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
#if !ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        if (force || request.replace_policy == SignReplacePolicy::Force) {
            return {
                SignApplyStatus::Unsupported,
                "the experimental live adapter permits blank placement into air only; "
                "force placement is disabled",
                0,
            };
        }
#endif
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

            const auto rollback = [this, &access, &before_sign, &request]() noexcept {
                try {
                    access->block->setData(*access->data, false);
                    auto restored = access->block->getData();
                    const bool structural_match =
                        restored && restored->getType() == access->data->getType() &&
                        fromEndstoneStates(restored->getBlockStates()) ==
                            fromEndstoneStates(access->data->getBlockStates());
                    if (!structural_match) return false;
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
                    if (before_sign) {
                        auto native = locateNativeSignActor(
                            server_, request.location, &text_bridge_);
                        if (!native.access) return false;
                        text_bridge_.applyText(*native.access->actor, SignSide::Front,
                                               before_sign->front);
                        text_bridge_.applyText(*native.access->actor, SignSide::Back,
                                               before_sign->back);
                        text_bridge_.setWaxed(*native.access->actor,
                                              before_sign->waxed);
                        text_bridge_.setLockedForEditingBy(
                            *native.access->actor,
                            before_sign->locked_for_editing_by);
                        text_bridge_.setProfanityFilters(
                            *native.access->actor,
                            before_sign->remote_profanity_filter_enabled,
                            before_sign->local_profanity_filter_enabled);
                        signalActorChanged(*native.access);
                        const auto verified = capture(request.location);
                        return verified &&
                               verified->revision == before_sign->revision;
                    }
#endif
                    return true;
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
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
                text_bridge_.applyText(*native.access->actor, SignSide::Front,
                                       request.front);
                text_bridge_.applyText(*native.access->actor, SignSide::Back,
                                       request.back);
                text_bridge_.setWaxed(*native.access->actor, request.waxed);
                auto lock_id = request.locked_for_editing_by;
                if (request.locked_for_editing_xuid && lock_id < 0) {
                    for (auto *online : server_.getOnlinePlayers()) {
                        if (!online ||
                            online->getXuid() != *request.locked_for_editing_xuid)
                            continue;
                        auto &handle = static_cast<endstone::core::EndstonePlayer &>(
                                           *online).getHandle();
                        lock_id = handle.getOrCreateUniqueID().raw_id;
                        break;
                    }
                    if (lock_id < 0) {
                        return fail_after_write(
                            "locked_for_editing_xuid did not identify an online player");
                    }
                }
                text_bridge_.setLockedForEditingBy(*native.access->actor, lock_id);
                text_bridge_.setProfanityFilters(
                    *native.access->actor,
                    request.remote_profanity_filter_enabled,
                    request.local_profanity_filter_enabled);
#endif
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
                    !states_match
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
                    || updated->front.lines != request.front.lines ||
                    updated->front.filtered_message != request.front.filtered_message ||
                    updated->front.text_object != request.front.text_object ||
                    updated->front.message_is_text_object != request.front.message_is_text_object ||
                    updated->front.argb != request.front.argb ||
                    updated->front.glowing != request.front.glowing ||
                    updated->front.hide_glow_outline != request.front.hide_glow_outline ||
                    updated->front.persist_formatting != request.front.persist_formatting ||
                    updated->front.owner_xuid != request.front.owner_xuid ||
                    updated->back.lines != request.back.lines ||
                    updated->back.filtered_message != request.back.filtered_message ||
                    updated->back.text_object != request.back.text_object ||
                    updated->back.message_is_text_object != request.back.message_is_text_object ||
                    updated->back.argb != request.back.argb ||
                    updated->back.glowing != request.back.glowing ||
                    updated->back.hide_glow_outline != request.back.hide_glow_outline ||
                    updated->back.persist_formatting != request.back.persist_formatting ||
                    updated->back.owner_xuid != request.back.owner_xuid ||
                    updated->waxed != request.waxed ||
                    updated->locked_for_editing_by != lock_id ||
                    updated->remote_profanity_filter_enabled !=
                        request.remote_profanity_filter_enabled ||
                    updated->local_profanity_filter_enabled !=
                        request.local_profanity_filter_enabled
#endif
                ) {
                    return fail_after_write(
                        "sign block was placed but identifier/state readback did not "
                        "match the request");
                }
                return {
                    SignApplyStatus::Applied,
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
                    "placed and read back a complete native sign payload",
#else
                    "placed a blank sign through the Endstone v0.11.6 block boundary",
#endif
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
#if !ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
        if (force || !request.expected_revision || *request.expected_revision == 0) {
            return {
                SignApplyStatus::Unsupported,
                "experimental removal requires a nonzero expected revision and force=false",
                current->revision,
            };
        }
#endif
        if (!force && request.expected_revision &&
            *request.expected_revision != current->revision) {
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
        struct TransactionLedger {
            SignOperation operation;
            std::optional<SignSnapshot> before;
            bool applied{};
        };

        auto capture_before = [this](const SignOperation &operation) {
            return std::visit(
                [this](const auto &entry) -> std::optional<SignSnapshot> {
                    using T = std::decay_t<decltype(entry)>;
                    if constexpr (std::is_same_v<T, SignPlaceRequest>) {
                        return capture(entry.location);
                    } else if constexpr (std::is_same_v<T, SignPatch>) {
                        return capture(entry.location);
                    } else {
                        return capture(entry.location);
                    }
                },
                operation);
        };

        auto apply_operation = [this, &transaction](const SignOperation &operation) {
            return std::visit(
                [this, &transaction](const auto &entry) -> SignApplyResult {
                    using T = std::decay_t<decltype(entry)>;
                    if constexpr (std::is_same_v<T, SignPlaceRequest>) {
                        return place(entry, transaction.force);
                    } else if constexpr (std::is_same_v<T, SignPatch>) {
                        return apply(entry, transaction.force);
                    } else {
                        return remove(entry, transaction.force);
                    }
                },
                operation);
        };

        auto clear_sign = [this](const SignLocation &location) {
            try {
                auto access = locatePublicBlock(server_, location);
                if (!access) return false;
                access->block->setType("minecraft:air", false);
                const auto readback = locatePublicBlock(server_, location);
                return readback && readback->data->getType() == "minecraft:air";
            } catch (...) {
                return false;
            }
        };

        auto restore_snapshot = [this](const SignSnapshot &snapshot) {
            try {
                auto access = locatePublicBlock(server_, snapshot.location);
                if (!access) return false;

                auto replacement =
                    createRegisteredBlockData(server_, snapshot.block_identifier, snapshot.states);
                if (!replacement.type_registered) return false;
                if (!replacement.data) return false;
                access->block->setData(*replacement.data, false);

                auto native =
                    locateNativeSignActor(server_, snapshot.location, &text_bridge_);
                if (native.access) {
                    if (text_bridge_.ready()) {
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
                        text_bridge_.applyText(*native.access->actor, SignSide::Front,
                                               snapshot.front);
                        text_bridge_.applyText(*native.access->actor, SignSide::Back,
                                               snapshot.back);
                        text_bridge_.setWaxed(*native.access->actor, snapshot.waxed);
                        text_bridge_.setLockedForEditingBy(
                            *native.access->actor,
                            snapshot.locked_for_editing_by);
                        text_bridge_.setProfanityFilters(
                            *native.access->actor,
                            snapshot.remote_profanity_filter_enabled,
                            snapshot.local_profanity_filter_enabled);
#else
                        try {
                            const auto before_front = flattenSignLines(snapshot.front.lines);
                            if (snapshot.front.owner_xuid.size() <=
                                    ExperimentalLinuxTextBridge::SafeTransferredMessageBytes &&
                                before_front.size() <=
                                    ExperimentalLinuxTextBridge::SafeTransferredMessageBytes) {
                                text_bridge_.setMessage(
                                    *native.access->actor, SignSide::Front, before_front,
                                    snapshot.front.owner_xuid);
                            }
                        } catch (...) {
                            // If restoring the optional text payload fails, continue with
                            // structural restoration only.
                        }
#endif
                        try {
                            const auto before_back = flattenSignLines(snapshot.back.lines);
                            if (snapshot.back.owner_xuid.size() <=
                                    ExperimentalLinuxTextBridge::SafeTransferredMessageBytes &&
                                before_back.size() <=
                                    ExperimentalLinuxTextBridge::SafeTransferredMessageBytes) {
                                text_bridge_.setMessage(
                                    *native.access->actor, SignSide::Back, before_back,
                                    snapshot.back.owner_xuid);
                            }
                        } catch (...) {
                            // If restoring the optional text payload fails, continue with
                            // structural restoration only.
                        }
                        try {
                            signalActorChanged(*native.access);
                        } catch (...) {
                            return false;
                        }
                    }
                }
                return true;
            } catch (...) {
                return false;
            }
        };

        auto rollback = [&](const std::vector<TransactionLedger> &ledger) {
            bool all_restored = true;
            for (auto it = ledger.rbegin(); it != ledger.rend(); ++it) {
                if (!it->applied) continue;
                bool restored = false;
                if (it->before) {
                    restored = restore_snapshot(*it->before);
                } else {
                    const auto *place =
                        std::get_if<SignPlaceRequest>(&it->operation);
                    if (place) {
                        restored = clear_sign(place->location);
                    }
                }
                all_restored = all_restored && restored;
            }
            return all_restored;
        };

        std::vector<SignApplyResult> operation_results;
        std::vector<TransactionLedger> ledger;
        operation_results.reserve(transaction.operations.size());
        ledger.reserve(transaction.operations.size());

        for (const auto &operation : transaction.operations) {
            auto before = capture_before(operation);
            const auto operation_result = apply_operation(operation);
            operation_results.push_back(operation_result);
            ledger.push_back(TransactionLedger{
                operation,
                std::move(before),
                operation_result.ok(),
            });
            if (!operation_result.ok()) {
                if (transaction.rollback_on_failure) {
                    const bool rolled_back = rollback(ledger);
                    return {
                        SignApplyStatus::TransactionFailed,
                        "transaction stopped: " + operation_result.message,
                        operation_results,
                        rolled_back,
                    };
                }
                return {
                    SignApplyStatus::TransactionFailed,
                    "transaction stopped: " + operation_result.message,
                    operation_results,
                    false,
                };
            }
        }

        return {
            SignApplyStatus::Applied,
            "transaction applied atomically",
            operation_results,
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
#if !ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
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
#endif
        if (player.getDimension().getName() != request.location.dimension) {
            return {
                SignApplyStatus::PermissionDenied,
                "player and sign must be in the same dimension",
                current->revision,
            };
        }
        auto native_actor =
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
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
            if (request.acquire_lock) {
                text_bridge_.setLockedForEditingBy(
                    *native_actor.access->actor,
                    native_player.getOrCreateUniqueID().raw_id);
                signalActorChanged(*native_actor.access);
            }
#endif
            const ::BlockPos position(request.location.x, request.location.y, request.location.z);
            native_player.openSign(position, request.side == SignSide::Front);
            return {
                SignApplyStatus::Applied,
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
                request.acquire_lock
                    ? "acquired the native editor lock and opened the requested sign side"
                    : "opened the requested sign side without changing its editor lock",
#else
                "sent the pinned Player::openSign UI request without claiming an "
                "editor lock",
#endif
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
#if ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
    using UpdateTextFromClient =
        void (*)(BlockActor *, const CompoundTag *, const BlockSource *);

    struct ReentryGuard {
        explicit ReentryGuard(bool &active) : active_(active) { active_ = true; }
        ~ReentryGuard() { active_ = false; }
        bool &active_;
    };

    [[nodiscard]] std::optional<SignLocation> locationFor(
        const BlockActor &actor, const BlockSource &source) const {
        auto *level = server_.getLevel();
        if (!level)
            return std::nullopt;

        std::array<std::int32_t, 3> coordinates{};
        constexpr std::size_t BlockPositionOffset = 0x8;
        std::memcpy(coordinates.data(),
                    reinterpret_cast<const std::byte *>(&actor) +
                        BlockPositionOffset,
                    sizeof(coordinates));
        for (auto *dimension : level->getDimensions()) {
            if (!dimension)
                continue;
            auto *exact_dimension =
                static_cast<endstone::core::EndstoneDimension *>(dimension);
            auto &candidate_source =
                exact_dimension->getHandle().getBlockSourceFromMainChunkSource();
            if (std::addressof(candidate_source) == std::addressof(source)) {
                return SignLocation{dimension->getName(), coordinates[0],
                                    coordinates[1], coordinates[2]};
            }
        }
        return std::nullopt;
    }

    [[nodiscard]] std::optional<SignActorContext> playerContext(
        const BlockActor &actor) const {
        const auto locked_id = text_bridge_.lockedForEditingBy(actor);
        if (locked_id < 0)
            return std::nullopt;
        for (auto *online : server_.getOnlinePlayers()) {
            if (!online)
                continue;
            auto &handle = static_cast<endstone::core::EndstonePlayer &>(*online)
                               .getHandle();
            if (handle.getOrCreateUniqueID().raw_id != locked_id)
                continue;
            SignActorContext context;
            context.origin = SignMutationOrigin::Player;
            context.actor_name = online->getName();
            context.actor_xuid = online->getXuid();
            return context;
        }
        return std::nullopt;
    }

    [[nodiscard]] static bool sameTextExceptOwner(const SignText &left,
                                                  const SignText &right) {
        if (left.message_is_text_object != right.message_is_text_object)
            return false;
        const bool same_message = left.message_is_text_object
                                      ? sameTextObject(left.text_object,
                                                       right.text_object)
                                      : left.lines == right.lines;
        return same_message &&
               left.filtered_message == right.filtered_message &&
               left.argb == right.argb && left.glowing == right.glowing &&
               left.hide_glow_outline == right.hide_glow_outline &&
               left.persist_formatting == right.persist_formatting;
    }

    [[nodiscard]] static bool sameTextObject(const std::string_view left,
                                             const std::string_view right) noexcept {
        try {
            return nlohmann::json::parse(left) == nlohmann::json::parse(right);
        } catch (...) {
            return false;
        }
    }

    [[nodiscard]] static bool sameText(const SignText &left,
                                       const SignText &right) {
        return sameTextExceptOwner(left, right) &&
               left.owner_xuid == right.owner_xuid;
    }

    [[nodiscard]] static bool samePayload(const SignSnapshot &left,
                                          const SignSnapshot &right) {
        return left.block_identifier == right.block_identifier &&
               left.states == right.states && sameText(left.front, right.front) &&
               sameText(left.back, right.back) && left.waxed == right.waxed &&
               left.locked_for_editing_by == right.locked_for_editing_by &&
               left.locked_for_editing_xuid == right.locked_for_editing_xuid &&
               left.remote_profanity_filter_enabled ==
                   right.remote_profanity_filter_enabled &&
               left.local_profanity_filter_enabled ==
                   right.local_profanity_filter_enabled;
    }

    void restoreText(BlockActor &actor, const SignSnapshot &snapshot) const {
        text_bridge_.applyText(actor, SignSide::Front, snapshot.front);
        text_bridge_.applyText(actor, SignSide::Back, snapshot.back);
        text_bridge_.setLockedForEditingBy(actor,
                                          snapshot.locked_for_editing_by);
        text_bridge_.setProfanityFilters(
            actor, snapshot.remote_profanity_filter_enabled,
            snapshot.local_profanity_filter_enabled);
    }

    void handlePlayerEdit(BlockActor &actor, const CompoundTag &payload,
                          const BlockSource &source) {
        static thread_local bool handling_player_edit = false;
        if (!update_text_original_)
            return;
        if (handling_player_edit) {
            update_text_original_(std::addressof(actor), std::addressof(payload),
                                  std::addressof(source));
            return;
        }
        ReentryGuard guard(handling_player_edit);

        const auto bus = event_bus_.lock();
        const auto location = locationFor(actor, source);
        const auto player = playerContext(actor);
        const bool has_front = payload.getCompound("FrontText") != nullptr;
        const bool has_back = payload.getCompound("BackText") != nullptr;
        if (!bus || !location || !player || (!has_front && !has_back)) {
            update_text_original_(std::addressof(actor), std::addressof(payload),
                                  std::addressof(source));
            return;
        }

        const auto before = capture(*location);
        if (!before) {
            update_text_original_(std::addressof(actor), std::addressof(payload),
                                  std::addressof(source));
            return;
        }

        std::optional<SignSnapshot> candidate;
        try {
            text_bridge_.applyClientPayload(actor, payload);
            candidate = capture(*location);
            if (!candidate) {
                restoreText(actor, *before);
                update_text_original_(std::addressof(actor),
                                      std::addressof(payload),
                                      std::addressof(source));
                return;
            }

            const bool front_changed =
                has_front && !sameTextExceptOwner(candidate->front, before->front);
            const bool back_changed =
                has_back && !sameTextExceptOwner(candidate->back, before->back);
            if (front_changed)
                text_bridge_.setOwnerXuid(actor, SignSide::Front,
                                          player->actor_xuid);
            if (back_changed)
                text_bridge_.setOwnerXuid(actor, SignSide::Back,
                                          player->actor_xuid);
            candidate = capture(*location);
            restoreText(actor, *before);

            if (!candidate || (!front_changed && !back_changed)) {
                update_text_original_(std::addressof(actor),
                                      std::addressof(payload),
                                      std::addressof(source));
                return;
            }
            candidate->locked_for_editing_by = -1;
            candidate->locked_for_editing_xuid.reset();
            candidate->revision = calculateSignRevision(*candidate);
        } catch (...) {
            try {
                restoreText(actor, *before);
            } catch (...) {
            }
            update_text_original_(std::addressof(actor), std::addressof(payload),
                                  std::addressof(source));
            return;
        }

        SignEvent received{SignEventKind::PlayerEditReceived,
                           *location,
                           *player,
                           before,
                           candidate,
                           true,
                           false,
                           {}};
        try {
            bus->publish(received);
        } catch (...) {
            update_text_original_(std::addressof(actor), std::addressof(payload),
                                  std::addressof(source));
            return;
        }
        if (received.cancelled) {
            text_bridge_.setLockedForEditingBy(actor, -1);
            auto current = locateNativeSignActor(server_, *location, &text_bridge_);
            if (current.access)
                signalActorChanged(*current.access);
            return;
        }

        update_text_original_(std::addressof(actor), std::addressof(payload),
                              std::addressof(source));
        const auto after = capture(*location);
        SignEvent changed{SignEventKind::AfterChange,
                          *location,
                          *player,
                          before,
                          after,
                          false,
                          false,
                          {}};
        try {
            bus->publish(changed);
        } catch (...) {
        }
    }

    static void updateTextFromClientHook(BlockActor *actor,
                                         const CompoundTag *payload,
                                         const BlockSource *source) {
        auto *owner = hook_owner_;
        if (!owner || !owner->update_text_original_ || !actor || !payload ||
            !source)
            return;
        owner->handlePlayerEdit(*actor, *payload, *source);
    }

    void installPlayerEditHook() {
#if defined(__linux__) && defined(__x86_64__)
        if (!exact_runtime_ || !text_bridge_.ready()) {
            hook_failure_ = "native text bridge is not ready";
            return;
        }
        if (hook_owner_) {
            hook_failure_ = "another Sign adapter already owns the player-edit hook";
            return;
        }
        hook_ = funchook_create();
        if (!hook_) {
            hook_failure_ = "funchook_create failed";
            return;
        }
        void *target = reinterpret_cast<void *>(
            text_bridge_.updateTextFromClientAddress());
        const auto prepared = funchook_prepare(
            hook_, &target,
            reinterpret_cast<void *>(&ExperimentalBds2630SignAdapter::
                                          updateTextFromClientHook));
        if (prepared != FUNCHOOK_ERROR_SUCCESS) {
            hook_failure_ = funchook_error_message(hook_);
            funchook_destroy(hook_);
            hook_ = nullptr;
            return;
        }
        update_text_original_ = reinterpret_cast<UpdateTextFromClient>(target);
        hook_owner_ = this;
        const auto installed = funchook_install(hook_, 0);
        if (installed != FUNCHOOK_ERROR_SUCCESS) {
            hook_failure_ = funchook_error_message(hook_);
            hook_owner_ = nullptr;
            update_text_original_ = nullptr;
            funchook_destroy(hook_);
            hook_ = nullptr;
            return;
        }
        hook_installed_ = true;
        hook_failure_.clear();
#else
        hook_failure_ = "player-edit hook is available only on Linux x64";
#endif
    }

    void uninstallPlayerEditHook() noexcept {
        if (hook_owner_ == this)
            hook_owner_ = nullptr;
        if (hook_) {
            if (hook_installed_)
                (void)funchook_uninstall(hook_, 0);
            (void)funchook_destroy(hook_);
        }
        hook_ = nullptr;
        update_text_original_ = nullptr;
        hook_installed_ = false;
    }

    static inline ExperimentalBds2630SignAdapter *hook_owner_{};
    std::weak_ptr<SignEventBus> event_bus_;
    funchook_t *hook_{};
    UpdateTextFromClient update_text_original_{};
    bool hook_installed_{};
    std::string hook_failure_;
#endif
    endstone::Server &server_;
    bool exact_runtime_{};
    ExperimentalLinuxTextBridge text_bridge_;
};

} // namespace

std::shared_ptr<ISignAdapter> makeExperimentalBds2630SignAdapter(endstone::Server &server) {
    return std::make_shared<ExperimentalBds2630SignAdapter>(server);
}

} // namespace endstone_sign
