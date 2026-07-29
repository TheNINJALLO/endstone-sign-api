#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <string>

namespace endstone_sign {

inline constexpr std::size_t SignLineCount = 4;
using SignLines = std::array<std::string, SignLineCount>;

struct SignText {
    SignLines lines{};
    std::string filtered_message;
    std::string text_object;
    bool message_is_text_object{};
    std::uint32_t argb{0xFF000000u};
    bool glowing{};
    bool hide_glow_outline{};
    bool persist_formatting{true};
    std::string owner_xuid;
};

struct SignTextPatch {
    std::optional<SignLines> lines;
    std::map<std::size_t, std::string> line_updates;
    std::optional<std::string> message;
    std::optional<std::string> filtered_message;
    std::optional<std::string> text_object;
    std::optional<bool> message_is_text_object;
    std::optional<std::uint32_t> argb;
    std::optional<bool> glowing;
    std::optional<bool> hide_glow_outline;
    std::optional<bool> persist_formatting;
    std::optional<std::string> owner_xuid;
};

struct SignValidationLimits {
    std::size_t max_line_bytes{384};
    std::size_t max_total_bytes{1536};
    std::size_t max_filtered_bytes{1536};
    std::size_t max_text_object_bytes{8192};
    std::size_t max_owner_bytes{128};
    bool allow_formatting_codes{true};
};

[[nodiscard]] std::string flattenSignLines(const SignLines &lines);
[[nodiscard]] std::optional<SignLines> splitSignMessage(
    const std::string &message,
    std::string *error = nullptr);
[[nodiscard]] bool isValidUtf8(const std::string &value) noexcept;
[[nodiscard]] std::optional<std::string> validateSignText(
    const SignText &text,
    const SignValidationLimits &limits = {});
[[nodiscard]] std::optional<std::string> validateTextPatch(
    const SignTextPatch &patch,
    const SignValidationLimits &limits = {});
[[nodiscard]] SignText applyTextPatch(const SignText &base, const SignTextPatch &patch);

} // namespace endstone_sign
