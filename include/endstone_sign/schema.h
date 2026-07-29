#pragma once

#include "endstone_sign/snapshot.h"

#include <cstdint>
#include <string>

namespace endstone_sign {

struct SignSideProjection {
    std::string text;
    std::string filtered_text;
    std::string text_object;
    bool message_is_text_object{};
    std::int32_t sign_text_color{-16777216};
    bool ignore_lighting{};
    bool hide_glow_outline{};
    bool persist_formatting{true};
    std::string text_owner;
};

struct SignNbtProjection {
    SignSideProjection front_text;
    SignSideProjection back_text;
    bool is_waxed{};
    std::int64_t locked_for_editing_by{-1};
};

[[nodiscard]] SignSideProjection makeSideProjection(const SignText &text);
[[nodiscard]] SignText signTextFromProjection(const SignSideProjection &projection);
[[nodiscard]] SignNbtProjection makeNbtProjection(const SignSnapshot &snapshot);
void applyNbtProjection(SignSnapshot &snapshot, const SignNbtProjection &projection);

} // namespace endstone_sign
