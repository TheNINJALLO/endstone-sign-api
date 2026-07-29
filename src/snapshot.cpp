#include "endstone_sign/snapshot.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <type_traits>

namespace endstone_sign {
namespace {

constexpr std::uint64_t FnvOffset = 14695981039346656037ull;
constexpr std::uint64_t FnvPrime = 1099511628211ull;

void hashBytes(std::uint64_t &hash, const void *data, std::size_t size) noexcept {
    const auto *bytes = static_cast<const unsigned char *>(data);
    for (std::size_t i = 0; i < size; ++i) {
        hash ^= bytes[i];
        hash *= FnvPrime;
    }
}

void hashString(std::uint64_t &hash, const std::string &value) noexcept {
    hashBytes(hash, value.data(), value.size());
    constexpr unsigned char Separator = 0xFF;
    hashBytes(hash, &Separator, 1);
}

template <typename T>
void hashScalar(std::uint64_t &hash, const T &value) noexcept {
    static_assert(std::is_trivially_copyable_v<T>);
    hashBytes(hash, &value, sizeof(value));
}

void hashText(std::uint64_t &hash, const SignText &text) noexcept {
    for (const auto &line : text.lines) hashString(hash, line);
    hashString(hash, text.filtered_message);
    hashString(hash, text.text_object);
    hashScalar(hash, text.message_is_text_object);
    hashScalar(hash, text.argb);
    hashScalar(hash, text.glowing);
    hashScalar(hash, text.hide_glow_outline);
    hashScalar(hash, text.persist_formatting);
    hashString(hash, text.owner_xuid);
}

} // namespace

std::uint64_t calculateSignRevision(const SignSnapshot &snapshot) noexcept {
    std::uint64_t hash = FnvOffset;
    hashString(hash, snapshot.location.dimension);
    hashScalar(hash, snapshot.location.x);
    hashScalar(hash, snapshot.location.y);
    hashScalar(hash, snapshot.location.z);
    hashString(hash, snapshot.block_identifier);
    hashScalar(hash, snapshot.kind);
    for (const auto &[key, value] : snapshot.states) {
        hashString(hash, key);
        const auto variant_index = value.index();
        hashScalar(hash, variant_index);
        std::visit([&hash](const auto &entry) {
            using T = std::decay_t<decltype(entry)>;
            if constexpr (std::is_same_v<T, std::string>) hashString(hash, entry);
            else hashScalar(hash, entry);
        }, value);
    }
    hashText(hash, snapshot.front);
    hashText(hash, snapshot.back);
    hashScalar(hash, snapshot.waxed);
    hashScalar(hash, snapshot.locked_for_editing_by);
    const bool has_lock_xuid = snapshot.locked_for_editing_xuid.has_value();
    hashScalar(hash, has_lock_xuid);
    if (snapshot.locked_for_editing_xuid) hashString(hash, *snapshot.locked_for_editing_xuid);
    hashScalar(hash, snapshot.remote_profanity_filter_enabled);
    hashScalar(hash, snapshot.local_profanity_filter_enabled);
    hashScalar(hash, snapshot.movable);
    hashScalar(hash, snapshot.actor_status);
    hashString(hash, snapshot.canonical_snbt);
    return hash;
}

} // namespace endstone_sign
