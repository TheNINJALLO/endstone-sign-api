#include "endstone_sign/schema.h"

namespace endstone_sign {

SignSideProjection makeSideProjection(const SignText &text) {
    SignSideProjection out;
    out.text = flattenSignLines(text.lines);
    out.filtered_text = text.filtered_message;
    out.text_object = text.text_object;
    out.message_is_text_object = text.message_is_text_object;
    out.sign_text_color = static_cast<std::int32_t>(text.argb);
    out.ignore_lighting = text.glowing;
    out.hide_glow_outline = text.hide_glow_outline;
    out.persist_formatting = text.persist_formatting;
    out.text_owner = text.owner_xuid;
    return out;
}

SignText signTextFromProjection(const SignSideProjection &projection) {
    SignText out;
    std::string error;
    if (const auto lines = splitSignMessage(projection.text, &error)) out.lines = *lines;
    out.filtered_message = projection.filtered_text;
    out.text_object = projection.text_object;
    out.message_is_text_object = projection.message_is_text_object;
    out.argb = static_cast<std::uint32_t>(projection.sign_text_color);
    out.glowing = projection.ignore_lighting;
    out.hide_glow_outline = projection.hide_glow_outline;
    out.persist_formatting = projection.persist_formatting;
    out.owner_xuid = projection.text_owner;
    return out;
}

SignNbtProjection makeNbtProjection(const SignSnapshot &snapshot) {
    return {
        makeSideProjection(snapshot.front),
        makeSideProjection(snapshot.back),
        snapshot.waxed,
        snapshot.locked_for_editing_by,
    };
}

void applyNbtProjection(SignSnapshot &snapshot, const SignNbtProjection &projection) {
    snapshot.front = signTextFromProjection(projection.front_text);
    snapshot.back = signTextFromProjection(projection.back_text);
    snapshot.waxed = projection.is_waxed;
    snapshot.locked_for_editing_by = projection.locked_for_editing_by;
    snapshot.revision = calculateSignRevision(snapshot);
}

} // namespace endstone_sign
