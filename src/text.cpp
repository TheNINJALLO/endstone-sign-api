#include "endstone_sign/text.h"

#include <limits>
#include <string>

namespace endstone_sign {
namespace {

bool containsForbiddenLineControl(const std::string &value) noexcept {
    return value.find('\0') != std::string::npos ||
           value.find('\n') != std::string::npos ||
           value.find('\r') != std::string::npos;
}

bool containsFormattingCode(const std::string &value) noexcept {
    constexpr unsigned char SectionLead = 0xC2;
    constexpr unsigned char SectionTail = 0xA7;
    for (std::size_t i = 0; i + 1 < value.size(); ++i) {
        if (static_cast<unsigned char>(value[i]) == SectionLead &&
            static_cast<unsigned char>(value[i + 1]) == SectionTail) {
            return true;
        }
    }
    return false;
}

std::optional<std::string> validateFreeText(
    const std::string &value,
    std::size_t maximum,
    const char *label) {
    if (!isValidUtf8(value)) return std::string(label) + " is not valid UTF-8";
    if (value.find('\0') != std::string::npos)
        return std::string(label) + " contains a NUL byte";
    if (value.size() > maximum)
        return std::string(label) + " exceeds the configured byte limit";
    return std::nullopt;
}

} // namespace

std::string flattenSignLines(const SignLines &lines) {
    std::string result;
    std::size_t size = SignLineCount - 1;
    for (const auto &line : lines) size += line.size();
    result.reserve(size);
    for (std::size_t i = 0; i < lines.size(); ++i) {
        if (i != 0) result.push_back('\n');
        result += lines[i];
    }
    return result;
}

std::optional<SignLines> splitSignMessage(const std::string &message, std::string *error) {
    if (!isValidUtf8(message)) {
        if (error) *error = "sign message is not valid UTF-8";
        return std::nullopt;
    }
    if (message.find('\0') != std::string::npos || message.find('\r') != std::string::npos) {
        if (error) *error = "sign message contains a forbidden control character";
        return std::nullopt;
    }

    SignLines lines{};
    std::size_t start = 0;
    std::size_t line = 0;
    while (true) {
        if (line >= SignLineCount) {
            if (error) *error = "sign message contains more than four lines";
            return std::nullopt;
        }
        const auto end = message.find('\n', start);
        lines[line++] = message.substr(
            start,
            end == std::string::npos ? std::string::npos : end - start);
        if (end == std::string::npos) break;
        start = end + 1;
    }
    return lines;
}

bool isValidUtf8(const std::string &value) noexcept {
    const auto *bytes = reinterpret_cast<const unsigned char *>(value.data());
    std::size_t i = 0;
    while (i < value.size()) {
        const unsigned char first = bytes[i];
        if (first <= 0x7F) {
            ++i;
            continue;
        }

        std::size_t width = 0;
        std::uint32_t codepoint = 0;
        if ((first & 0xE0) == 0xC0) {
            width = 2;
            codepoint = first & 0x1F;
            if (codepoint == 0) return false;
        } else if ((first & 0xF0) == 0xE0) {
            width = 3;
            codepoint = first & 0x0F;
        } else if ((first & 0xF8) == 0xF0) {
            width = 4;
            codepoint = first & 0x07;
        } else {
            return false;
        }
        if (i + width > value.size()) return false;
        for (std::size_t j = 1; j < width; ++j) {
            const unsigned char next = bytes[i + j];
            if ((next & 0xC0) != 0x80) return false;
            codepoint = (codepoint << 6) | (next & 0x3F);
        }
        if ((width == 2 && codepoint < 0x80) ||
            (width == 3 && codepoint < 0x800) ||
            (width == 4 && codepoint < 0x10000) ||
            codepoint > 0x10FFFF ||
            (codepoint >= 0xD800 && codepoint <= 0xDFFF)) {
            return false;
        }
        i += width;
    }
    return true;
}

std::optional<std::string> validateSignText(
    const SignText &text,
    const SignValidationLimits &limits) {
    std::size_t total = 0;
    for (std::size_t index = 0; index < text.lines.size(); ++index) {
        const auto &line = text.lines[index];
        if (!isValidUtf8(line))
            return "line " + std::to_string(index + 1) + " is not valid UTF-8";
        if (containsForbiddenLineControl(line))
            return "line " + std::to_string(index + 1) +
                   " contains a forbidden control character";
        if (!limits.allow_formatting_codes && containsFormattingCode(line))
            return "line " + std::to_string(index + 1) + " contains a formatting code";
        if (line.size() > limits.max_line_bytes)
            return "line " + std::to_string(index + 1) +
                   " exceeds the configured byte limit";
        if (total > std::numeric_limits<std::size_t>::max() - line.size())
            return "sign text size overflow";
        total += line.size();
    }
    if (total > limits.max_total_bytes)
        return "sign text exceeds the configured total byte limit";

    if (const auto error = validateFreeText(
            text.filtered_message, limits.max_filtered_bytes, "filtered message")) {
        return error;
    }
    if (text.filtered_message.find('\r') != std::string::npos)
        return "filtered message contains a carriage return";

    if (const auto error = validateFreeText(
            text.text_object, limits.max_text_object_bytes, "text object")) {
        return error;
    }
    if (const auto error = validateFreeText(
            text.owner_xuid, limits.max_owner_bytes, "text owner XUID")) {
        return error;
    }
    return std::nullopt;
}

std::optional<std::string> validateTextPatch(
    const SignTextPatch &patch,
    const SignValidationLimits &limits) {
    if (patch.lines && patch.message)
        return "whole-line replacement and message replacement cannot be combined";
    for (const auto &[index, line] : patch.line_updates) {
        if (index >= SignLineCount) return "line update index must be between 0 and 3";
        if (!isValidUtf8(line)) return "line update is not valid UTF-8";
        if (containsForbiddenLineControl(line))
            return "line update contains a forbidden control character";
        if (!limits.allow_formatting_codes && containsFormattingCode(line))
            return "line update contains a formatting code";
        if (line.size() > limits.max_line_bytes)
            return "line update exceeds the configured byte limit";
    }
    if (patch.message) {
        std::string error;
        if (!splitSignMessage(*patch.message, &error)) return error;
    }
    if (patch.filtered_message) {
        if (const auto error = validateFreeText(
                *patch.filtered_message, limits.max_filtered_bytes, "filtered message")) {
            return error;
        }
        if (patch.filtered_message->find('\r') != std::string::npos)
            return "filtered message contains a carriage return";
    }
    if (patch.text_object) {
        if (const auto error = validateFreeText(
                *patch.text_object, limits.max_text_object_bytes, "text object")) {
            return error;
        }
    }
    if (patch.owner_xuid) {
        if (const auto error = validateFreeText(
                *patch.owner_xuid, limits.max_owner_bytes, "text owner XUID")) {
            return error;
        }
    }
    return std::nullopt;
}

SignText applyTextPatch(const SignText &base, const SignTextPatch &patch) {
    SignText result = base;
    if (patch.lines) result.lines = *patch.lines;
    if (patch.message) {
        std::string ignored;
        if (const auto lines = splitSignMessage(*patch.message, &ignored)) result.lines = *lines;
    }
    for (const auto &[index, line] : patch.line_updates) {
        if (index < SignLineCount) result.lines[index] = line;
    }
    if (patch.filtered_message) result.filtered_message = *patch.filtered_message;
    if (patch.text_object) result.text_object = *patch.text_object;
    if (patch.message_is_text_object) result.message_is_text_object = *patch.message_is_text_object;
    if (patch.argb) result.argb = *patch.argb;
    if (patch.glowing) result.glowing = *patch.glowing;
    if (patch.hide_glow_outline) result.hide_glow_outline = *patch.hide_glow_outline;
    if (patch.persist_formatting) result.persist_formatting = *patch.persist_formatting;
    if (patch.owner_xuid) result.owner_xuid = *patch.owner_xuid;
    return result;
}

} // namespace endstone_sign
