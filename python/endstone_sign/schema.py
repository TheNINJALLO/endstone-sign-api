from __future__ import annotations

from dataclasses import dataclass, replace

from .model import SignSnapshot, SignText, calculate_revision, flatten_lines, split_message


@dataclass(frozen=True, slots=True)
class SignSideProjection:
    text: str = ""
    filtered_text: str = ""
    text_object: str = ""
    message_is_text_object: bool = False
    sign_text_color: int = -16777216
    ignore_lighting: bool = False
    hide_glow_outline: bool = False
    persist_formatting: bool = True
    text_owner: str = ""


@dataclass(frozen=True, slots=True)
class SignNbtProjection:
    front_text: SignSideProjection = SignSideProjection()
    back_text: SignSideProjection = SignSideProjection()
    is_waxed: bool = False
    locked_for_editing_by: int = -1


def make_side_projection(text: SignText) -> SignSideProjection:
    signed_color = text.argb if text.argb < 0x80000000 else text.argb - 0x100000000
    return SignSideProjection(
        text=flatten_lines(text.lines),
        filtered_text=text.filtered_message,
        text_object=text.text_object,
        message_is_text_object=text.message_is_text_object,
        sign_text_color=signed_color,
        ignore_lighting=text.glowing,
        hide_glow_outline=text.hide_glow_outline,
        persist_formatting=text.persist_formatting,
        text_owner=text.owner_xuid,
    )


def sign_text_from_projection(projection: SignSideProjection) -> SignText:
    return SignText(
        lines=split_message(projection.text),
        filtered_message=projection.filtered_text,
        text_object=projection.text_object,
        message_is_text_object=projection.message_is_text_object,
        argb=projection.sign_text_color & 0xFFFFFFFF,
        glowing=projection.ignore_lighting,
        hide_glow_outline=projection.hide_glow_outline,
        persist_formatting=projection.persist_formatting,
        owner_xuid=projection.text_owner,
    )


def make_nbt_projection(snapshot: SignSnapshot) -> SignNbtProjection:
    return SignNbtProjection(
        front_text=make_side_projection(snapshot.front),
        back_text=make_side_projection(snapshot.back),
        is_waxed=snapshot.waxed,
        locked_for_editing_by=snapshot.locked_for_editing_by,
    )


def apply_nbt_projection(snapshot: SignSnapshot, projection: SignNbtProjection) -> SignSnapshot:
    result = replace(
        snapshot,
        front=sign_text_from_projection(projection.front_text),
        back=sign_text_from_projection(projection.back_text),
        waxed=projection.is_waxed,
        locked_for_editing_by=projection.locked_for_editing_by,
    )
    return replace(result, revision=calculate_revision(result))
