#include "endstone_sign/live_service.h"
#include "endstone_sign/live_probe_service.h"

#include <endstone/player.h>
#include <endstone/plugin/service_manager.h>
#include <endstone/server.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <array>
#include <limits>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace py = pybind11;

#ifndef ENDSTONE_SIGN_VERSION
#define ENDSTONE_SIGN_VERSION "0.2.0"
#endif

namespace endstone_sign {
namespace {

std::shared_ptr<LiveSignService> loadService(endstone::Server &server) {
    return server.getServiceManager().load<LiveSignService>(std::string(SignServiceName));
}

std::shared_ptr<LiveSignProbeService> loadProbeService(endstone::Server &server) {
    return server.getServiceManager().load<LiveSignProbeService>(
        std::string(SignProbeServiceName));
}

SignLocation location(std::string dimension, std::int32_t x, std::int32_t y,
                      std::int32_t z) {
    return {std::move(dimension), x, y, z};
}

py::dict resultToDict(const SignApplyResult &result) {
    py::dict out;
    out["ok"] = result.ok();
    out["status"] = std::string(signApplyStatusName(result.status));
    out["message"] = result.message;
    out["revision"] = result.resulting_revision;
    return out;
}

py::dict transactionResultToDict(const SignTransactionResult &result) {
    py::dict out;
    out["ok"] = result.ok();
    out["status"] = std::string(signApplyStatusName(result.status));
    out["message"] = result.message;
    py::list operations;
    for (const auto &operation : result.operation_results)
        operations.append(resultToDict(operation));
    out["operation_results"] = std::move(operations);
    out["rolled_back"] = result.rolled_back;
    return out;
}

py::dict textToDict(const SignText &text) {
    py::dict out;
    out["lines"] = text.lines;
    out["filtered_message"] = text.filtered_message;
    out["text_object"] = text.text_object;
    out["message_is_text_object"] = text.message_is_text_object;
    out["argb"] = text.argb;
    out["glowing"] = text.glowing;
    out["hide_glow_outline"] = text.hide_glow_outline;
    out["persist_formatting"] = text.persist_formatting;
    out["owner_xuid"] = text.owner_xuid;
    return out;
}

py::dict snapshotToDict(const SignSnapshot &snapshot) {
    py::dict out;
    out["found"] = true;
    out["dimension"] = snapshot.location.dimension;
    out["x"] = snapshot.location.x;
    out["y"] = snapshot.location.y;
    out["z"] = snapshot.location.z;
    out["block_identifier"] = snapshot.block_identifier;
    out["kind"] = std::string(signKindName(snapshot.kind));
    out["states"] = snapshot.states;
    out["front"] = textToDict(snapshot.front);
    out["back"] = textToDict(snapshot.back);
    out["waxed"] = snapshot.waxed;
    out["locked_for_editing_by"] = snapshot.locked_for_editing_by;
    out["locked_for_editing_xuid"] = snapshot.locked_for_editing_xuid
                                             ? py::cast(*snapshot.locked_for_editing_xuid)
                                             : py::none();
    out["remote_profanity_filter_enabled"] =
        snapshot.remote_profanity_filter_enabled;
    out["local_profanity_filter_enabled"] =
        snapshot.local_profanity_filter_enabled;
    out["movable"] = snapshot.movable;
    out["actor_status"] = std::string(signActorStatusName(snapshot.actor_status));
    out["canonical_snbt"] = snapshot.canonical_snbt;
    out["revision"] = snapshot.revision;
    return out;
}

SignLines requireLines(const std::vector<std::string> &lines) {
    if (lines.size() != SignLineCount)
        throw py::value_error("exactly four sign lines are required");
    SignLines result{};
    std::copy(lines.begin(), lines.end(), result.begin());
    return result;
}

bool available(endstone::Server &server) noexcept {
    try {
        return static_cast<bool>(loadService(server));
    } catch (...) {
        return false;
    }
}

py::dict status(endstone::Server &server) {
    py::dict out;
    const auto service = loadService(server);
    out["available"] = static_cast<bool>(service);
    if (!service) return out;
    const auto caps = service->capabilities();
    out["adapter"] = service->adapterName();
    out["complete_control"] = caps.completeControl();
    py::dict capabilities;
#define ENDSTONE_SIGN_CAP(name) capabilities[#name] = caps.name
    ENDSTONE_SIGN_CAP(capture);
    ENDSTONE_SIGN_CAP(place);
    ENDSTONE_SIGN_CAP(remove);
    ENDSTONE_SIGN_CAP(replace);
    ENDSTONE_SIGN_CAP(clone);
    ENDSTONE_SIGN_CAP(move);
    ENDSTONE_SIGN_CAP(atomic_transactions);
    ENDSTONE_SIGN_CAP(read_text);
    ENDSTONE_SIGN_CAP(write_text);
    ENDSTONE_SIGN_CAP(front_and_back);
    ENDSTONE_SIGN_CAP(per_line_write);
    ENDSTONE_SIGN_CAP(text_objects);
    ENDSTONE_SIGN_CAP(filtered_text);
    ENDSTONE_SIGN_CAP(owner_xuid);
    ENDSTONE_SIGN_CAP(text_color);
    ENDSTONE_SIGN_CAP(glowing);
    ENDSTONE_SIGN_CAP(hide_glow_outline);
    ENDSTONE_SIGN_CAP(persist_formatting);
    ENDSTONE_SIGN_CAP(waxed);
    ENDSTONE_SIGN_CAP(editor_lock);
    ENDSTONE_SIGN_CAP(open_editor);
    ENDSTONE_SIGN_CAP(player_edit_events);
    ENDSTONE_SIGN_CAP(api_edit_events);
    ENDSTONE_SIGN_CAP(client_updates);
    ENDSTONE_SIGN_CAP(restart_persistence);
    ENDSTONE_SIGN_CAP(exact_build_match);
    ENDSTONE_SIGN_CAP(exact_binary_hash_match);
    ENDSTONE_SIGN_CAP(symbols_validated);
    ENDSTONE_SIGN_CAP(stage_probe_passed);
#undef ENDSTONE_SIGN_CAP
    out["capabilities"] = capabilities;
    return out;
}

py::dict capture(endstone::Server &server, const std::string &dimension,
                 std::int32_t x, std::int32_t y, std::int32_t z) {
    const auto service = loadService(server);
    if (!service) {
        py::dict out;
        out["found"] = false;
        out["error"] = "service unavailable";
        return out;
    }
    const auto snapshot = service->capture(location(dimension, x, y, z));
    if (!snapshot) {
        py::dict out;
        out["found"] = false;
        return out;
    }
    return snapshotToDict(*snapshot);
}

py::dict setText(endstone::Server &server, const std::string &dimension,
                 std::int32_t x, std::int32_t y, std::int32_t z,
                 const std::string &side, const std::vector<std::string> &lines,
                 std::optional<std::uint32_t> argb, std::optional<bool> glowing,
                 std::optional<bool> waxed, bool force,
                 std::optional<std::uint64_t> expected_revision) {
    const auto service = loadService(server);
    if (!service) return resultToDict({SignApplyStatus::AdapterUnavailable,
                                      "service unavailable", 0});
    SignTextPatch text;
    text.lines = requireLines(lines);
    text.argb = argb;
    text.glowing = glowing;
    SignPatch patch;
    patch.location = location(dimension, x, y, z);
    patch.expected_revision = expected_revision;
    patch.waxed = waxed;
    if (side == "front") patch.front = std::move(text);
    else if (side == "back") patch.back = std::move(text);
    else throw py::value_error("side must be 'front' or 'back'");
    return resultToDict(service->apply(patch, force));
}

py::dict setExtendedText(
    endstone::Server &server, const std::string &dimension, std::int32_t x,
    std::int32_t y, std::int32_t z, const std::string &side,
    std::optional<std::string> filtered_message,
    std::optional<std::string> text_object,
    std::optional<bool> message_is_text_object,
    std::optional<std::string> owner_xuid,
    std::optional<bool> hide_glow_outline,
    std::optional<bool> persist_formatting, bool force,
    std::optional<std::uint64_t> expected_revision) {
    const auto service = loadService(server);
    if (!service) return resultToDict({SignApplyStatus::AdapterUnavailable,
                                      "service unavailable", 0});
    SignTextPatch text;
    text.filtered_message = std::move(filtered_message);
    text.text_object = std::move(text_object);
    text.message_is_text_object = message_is_text_object;
    text.owner_xuid = std::move(owner_xuid);
    text.hide_glow_outline = hide_glow_outline;
    text.persist_formatting = persist_formatting;
    SignPatch patch;
    patch.location = location(dimension, x, y, z);
    patch.expected_revision = expected_revision;
    if (side == "front") patch.front = std::move(text);
    else if (side == "back") patch.back = std::move(text);
    else throw py::value_error("side must be 'front' or 'back'");
    return resultToDict(service->apply(patch, force));
}

py::dict setEditorLock(
    endstone::Server &server, const std::string &dimension, std::int32_t x,
    std::int32_t y, std::int32_t z, std::int64_t locked_for_editing_by,
    std::optional<std::string> locked_for_editing_xuid, bool force,
    std::optional<std::uint64_t> expected_revision) {
    const auto service = loadService(server);
    if (!service) return resultToDict({SignApplyStatus::AdapterUnavailable,
                                      "service unavailable", 0});
    SignPatch patch;
    patch.location = location(dimension, x, y, z);
    patch.expected_revision = expected_revision;
    patch.locked_for_editing_by = locked_for_editing_by;
    patch.locked_for_editing_xuid = std::move(locked_for_editing_xuid);
    return resultToDict(service->apply(patch, force));
}

SignStates requireStates(const py::dict &states) {
    SignStates result;
    for (const auto &[raw_key, raw_value] : states) {
        if (!py::isinstance<py::str>(raw_key))
            throw py::value_error("block-state keys must be strings");
        const auto key = py::cast<std::string>(raw_key);
        if (py::isinstance<py::bool_>(raw_value)) {
            result.insert_or_assign(key, py::cast<bool>(raw_value));
        } else if (py::isinstance<py::int_>(raw_value)) {
            const auto value = py::cast<std::int64_t>(raw_value);
            if (value < std::numeric_limits<std::int32_t>::min() ||
                value > std::numeric_limits<std::int32_t>::max()) {
                throw py::value_error("integer block state exceeds signed 32-bit range");
            }
            result.insert_or_assign(key, static_cast<std::int32_t>(value));
        } else if (py::isinstance<py::str>(raw_value)) {
            result.insert_or_assign(key, py::cast<std::string>(raw_value));
        } else {
            throw py::value_error("block-state values must be bool, int, or string");
        }
    }
    return result;
}

py::dict replaceSign(
    endstone::Server &server, const std::string &dimension, std::int32_t x,
    std::int32_t y, std::int32_t z, const std::string &block_identifier,
    const py::dict &states, bool force,
    std::optional<std::uint64_t> expected_revision) {
    const auto service = loadService(server);
    if (!service) return resultToDict({SignApplyStatus::AdapterUnavailable,
                                      "service unavailable", 0});
    const auto target = location(dimension, x, y, z);
    const auto current = service->capture(target);
    if (!current) return resultToDict({SignApplyStatus::NotASign,
                                      "replacement target is not a sign", 0});
    SignPatch patch;
    patch.location = target;
    patch.expected_revision = expected_revision;
    patch.block_identifier = block_identifier;
    patch.state_updates = requireStates(states);
    for (const auto &entry : current->states) {
        if (!patch.state_updates.contains(entry.first))
            patch.state_removals.insert(entry.first);
    }
    return resultToDict(service->apply(patch, force));
}

py::dict place(endstone::Server &server, const std::string &dimension,
               std::int32_t x, std::int32_t y, std::int32_t z,
               const std::string &block_identifier, const py::dict &states) {
    const auto service = loadService(server);
    if (!service) return resultToDict({SignApplyStatus::AdapterUnavailable,
                                      "service unavailable", 0});
    SignPlaceRequest request;
    request.location = location(dimension, x, y, z);
    request.block_identifier = block_identifier;
    request.states = requireStates(states);
    return resultToDict(service->place(request, false));
}

py::dict remove(endstone::Server &server, const std::string &dimension,
                std::int32_t x, std::int32_t y, std::int32_t z,
                bool force, std::optional<std::uint64_t> expected_revision) {
    const auto service = loadService(server);
    if (!service) return resultToDict({SignApplyStatus::AdapterUnavailable,
                                      "service unavailable", 0});
    SignRemoveRequest request;
    request.location = location(dimension, x, y, z);
    request.expected_revision = expected_revision;
    return resultToDict(service->remove(request, force));
}

py::dict cloneSign(
    endstone::Server &server, const std::string &dimension,
    std::int32_t source_x, std::int32_t source_y, std::int32_t source_z,
    std::int32_t destination_x, std::int32_t destination_y,
    std::int32_t destination_z, bool copy_editor_lock, bool force,
    std::optional<std::uint64_t> expected_source_revision) {
    const auto service = loadService(server);
    if (!service) return resultToDict({SignApplyStatus::AdapterUnavailable,
                                      "service unavailable", 0});
    SignCloneRequest request;
    request.source = location(dimension, source_x, source_y, source_z);
    request.destination =
        location(dimension, destination_x, destination_y, destination_z);
    request.expected_source_revision = expected_source_revision;
    request.copy_editor_lock = copy_editor_lock;
    return resultToDict(service->cloneSign(request, force));
}

py::dict moveSign(
    endstone::Server &server, const std::string &dimension,
    std::int32_t source_x, std::int32_t source_y, std::int32_t source_z,
    std::int32_t destination_x, std::int32_t destination_y,
    std::int32_t destination_z, bool copy_editor_lock, bool force,
    std::optional<std::uint64_t> expected_source_revision) {
    const auto service = loadService(server);
    if (!service) return resultToDict({SignApplyStatus::AdapterUnavailable,
                                      "service unavailable", 0});
    SignMoveRequest request;
    request.source = location(dimension, source_x, source_y, source_z);
    request.destination =
        location(dimension, destination_x, destination_y, destination_z);
    request.expected_source_revision = expected_source_revision;
    request.copy_editor_lock = copy_editor_lock;
    return resultToDict(service->moveSign(request, force));
}

py::dict probeAtomicRejection(
    endstone::Server &server, const std::string &dimension,
    std::int32_t first_x, std::int32_t first_y, std::int32_t first_z,
    std::int32_t blocked_x, std::int32_t blocked_y, std::int32_t blocked_z,
    const std::string &block_identifier, const py::dict &states,
    std::optional<std::uint64_t> expected_revision) {
    const auto service = loadService(server);
    if (!service) return resultToDict({SignApplyStatus::AdapterUnavailable,
                                      "service unavailable", 0});
    const auto first_location = location(dimension, first_x, first_y, first_z);
    const auto first_before = service->capture(first_location);
    if (!first_before) {
        py::dict out;
        out["ok"] = false;
        out["status"] = "not_a_sign";
        out["message"] = "the atomic probe source sign must exist";
        return out;
    }
    if (expected_revision && *expected_revision != first_before->revision) {
        return resultToDict({SignApplyStatus::Conflict,
                             "atomic probe source revision changed",
                             first_before->revision});
    }
    SignPatch first;
    first.location = first_location;
    first.expected_revision = first_before->revision;
    SignTextPatch first_text;
    first_text.line_updates[0] =
        first_before->front.lines[0] == "a7tx" ? "a7ty" : "a7tx";
    first.front = std::move(first_text);
    SignPlaceRequest second;
    second.location = location(dimension, blocked_x, blocked_y, blocked_z);
    second.block_identifier = block_identifier;
    second.states = requireStates(states);
    second.replace_policy = SignReplacePolicy::RequireAir;
    SignTransaction transaction;
    transaction.rollback_on_failure = true;
    transaction.audit_reason = "alpha7 atomic no-partial-write probe";
    transaction.operations.emplace_back(std::move(first));
    transaction.operations.emplace_back(std::move(second));
    const auto result = service->transact(transaction);
    const auto first_after = service->capture(first_location);
    auto out = transactionResultToDict(result);
    const bool unchanged = first_after &&
                           first_after->revision == first_before->revision;
    const bool operation_shape =
        result.status == SignApplyStatus::TransactionFailed &&
        result.operation_results.size() == 2 &&
        result.operation_results[0].status == SignApplyStatus::Applied &&
        result.operation_results[1].status == SignApplyStatus::BlockOccupied;
    out["transaction_rejected"] = operation_shape;
    out["first_sign_unchanged"] = unchanged;
    out["before_revision"] = first_before->revision;
    out["after_revision"] = first_after ? first_after->revision : 0;
    out["ok"] = operation_shape && result.rolled_back && unchanged;
    return out;
}

std::string_view eventKindName(const SignEventKind kind) noexcept {
    switch (kind) {
    case SignEventKind::BeforePlace: return "before_place";
    case SignEventKind::AfterPlace: return "after_place";
    case SignEventKind::BeforeChange: return "before_change";
    case SignEventKind::AfterChange: return "after_change";
    case SignEventKind::BeforeRemove: return "before_remove";
    case SignEventKind::AfterRemove: return "after_remove";
    case SignEventKind::BeforeOpenEditor: return "before_open_editor";
    case SignEventKind::AfterOpenEditor: return "after_open_editor";
    case SignEventKind::BeforeLock: return "before_lock";
    case SignEventKind::AfterLock: return "after_lock";
    case SignEventKind::BeforeUnlock: return "before_unlock";
    case SignEventKind::AfterUnlock: return "after_unlock";
    case SignEventKind::PlayerEditReceived: return "player_edit_received";
    }
    return "before_change";
}

std::string_view mutationOriginName(const SignMutationOrigin origin) noexcept {
    switch (origin) {
    case SignMutationOrigin::Api: return "api";
    case SignMutationOrigin::Player: return "player";
    case SignMutationOrigin::Command: return "command";
    case SignMutationOrigin::Structure: return "structure";
    case SignMutationOrigin::WorldLoad: return "world_load";
    case SignMutationOrigin::Unknown: return "unknown";
    }
    return "unknown";
}

py::dict eventToDict(const SignEvent &event) {
    py::dict out;
    out["kind"] = eventKindName(event.kind);
    out["location"] = py::make_tuple(
        event.location.dimension, event.location.x, event.location.y,
        event.location.z);
    py::dict actor;
    actor["origin"] = mutationOriginName(event.actor.origin);
    actor["name"] = event.actor.actor_name;
    actor["xuid"] = event.actor.actor_xuid;
    actor["plugin_name"] = event.actor.plugin_name;
    out["actor"] = std::move(actor);
    if (event.before)
        out["before"] = snapshotToDict(*event.before);
    else
        out["before"] = py::none();
    if (event.after)
        out["after"] = snapshotToDict(*event.after);
    else
        out["after"] = py::none();
    out["cancellable"] = event.cancellable;
    out["cancelled"] = event.cancelled;
    out["cancellation_reason"] = event.cancellation_reason;
    return out;
}

std::size_t addEventListener(endstone::Server &server, py::function callback) {
    const auto service = loadService(server);
    if (!service)
        throw std::runtime_error("endstone:sign:v2 service is unavailable");
    auto retained = std::make_shared<py::function>(std::move(callback));
    return service->addEventListener([retained](SignEvent &event) {
        py::gil_scoped_acquire gil;
        auto payload = eventToDict(event);
        const py::object response = (*retained)(payload);
        if (!event.cancellable)
            return;

        bool cancelled = payload["cancelled"].cast<bool>();
        std::string reason = payload["cancellation_reason"].cast<std::string>();
        if (py::isinstance<py::bool_>(response)) {
            cancelled = response.cast<bool>();
        } else if (py::isinstance<py::str>(response)) {
            cancelled = true;
            reason = response.cast<std::string>();
        } else if (py::isinstance<py::dict>(response)) {
            const auto decision = response.cast<py::dict>();
            if (decision.contains("cancelled"))
                cancelled = decision["cancelled"].cast<bool>();
            if (decision.contains("reason"))
                reason = decision["reason"].cast<std::string>();
        }
        event.cancelled = cancelled;
        if (cancelled)
            event.cancellation_reason = std::move(reason);
    });
}

bool removeEventListener(endstone::Server &server,
                         const std::size_t listener_id) {
    const auto service = loadService(server);
    return service && service->removeEventListener(listener_id);
}

py::dict probeApiEventCancellation(
    endstone::Server &server, const std::string &dimension, std::int32_t x,
    std::int32_t y, std::int32_t z,
    std::optional<std::uint64_t> expected_revision) {
    const auto probe_service = loadProbeService(server);
    if (!probe_service)
        return resultToDict({SignApplyStatus::AdapterUnavailable,
                             "probe service unavailable", 0});
    const auto target = location(dimension, x, y, z);
    const auto result = probe_service->probeApiEventCancellation(
        target, expected_revision);
    auto out = resultToDict(result.apply_result);
    out["event_observed"] = result.event_observed;
    out["event_cancelled"] = result.event_cancelled;
    out["state_unchanged"] = result.state_unchanged;
    out["listener_removed"] = result.listener_removed;
    out["ok"] = result.ok();
    return out;
}

py::dict openEditor(endstone::Server &server, endstone::Player &player,
                    const std::string &dimension, std::int32_t x,
                    std::int32_t y, std::int32_t z, const std::string &side,
                    bool acquire_lock, bool bypass_wax) {
    const auto service = loadService(server);
    if (!service) return resultToDict({SignApplyStatus::AdapterUnavailable,
                                      "service unavailable", 0});
    SignOpenEditorRequest request;
    request.location = location(dimension, x, y, z);
    if (side == "front") request.side = SignSide::Front;
    else if (side == "back") request.side = SignSide::Back;
    else throw py::value_error("side must be 'front' or 'back'");
    request.acquire_lock = acquire_lock;
    request.bypass_wax = bypass_wax;
    return resultToDict(service->openEditor(player, request));
}

} // namespace
} // namespace endstone_sign

PYBIND11_MODULE(_endstone_sign_live, module) {
    module.doc() = "Live Python bridge to endstone:sign:v2";
    module.attr("__version__") = ENDSTONE_SIGN_VERSION;
    module.def("available", &endstone_sign::available, py::arg("server"));
    module.def("status", &endstone_sign::status, py::arg("server"));
    module.def("add_event_listener", &endstone_sign::addEventListener,
               py::arg("server"), py::arg("callback"));
    module.def("remove_event_listener", &endstone_sign::removeEventListener,
               py::arg("server"), py::arg("listener_id"));
    module.def("capture", &endstone_sign::capture, py::arg("server"),
               py::arg("dimension"), py::arg("x"), py::arg("y"), py::arg("z"));
    module.def("set_text", &endstone_sign::setText, py::arg("server"),
               py::arg("dimension"), py::arg("x"), py::arg("y"), py::arg("z"),
               py::arg("side"), py::arg("lines"), py::arg("argb") = py::none(),
               py::arg("glowing") = py::none(), py::arg("waxed") = py::none(),
               py::arg("force") = false,
               py::arg("expected_revision") = py::none());
    module.def("set_extended_text", &endstone_sign::setExtendedText,
               py::arg("server"), py::arg("dimension"), py::arg("x"),
               py::arg("y"), py::arg("z"), py::arg("side"),
               py::arg("filtered_message") = py::none(),
               py::arg("text_object") = py::none(),
               py::arg("message_is_text_object") = py::none(),
               py::arg("owner_xuid") = py::none(),
               py::arg("hide_glow_outline") = py::none(),
               py::arg("persist_formatting") = py::none(),
               py::arg("force") = false,
               py::arg("expected_revision") = py::none());
    module.def("set_editor_lock", &endstone_sign::setEditorLock,
               py::arg("server"), py::arg("dimension"), py::arg("x"),
               py::arg("y"), py::arg("z"),
               py::arg("locked_for_editing_by"),
               py::arg("locked_for_editing_xuid") = py::none(),
               py::arg("force") = false,
               py::arg("expected_revision") = py::none());
    module.def("place", &endstone_sign::place, py::arg("server"),
               py::arg("dimension"), py::arg("x"), py::arg("y"), py::arg("z"),
               py::arg("block_identifier"), py::arg("states"));
    module.def("replace", &endstone_sign::replaceSign, py::arg("server"),
               py::arg("dimension"), py::arg("x"), py::arg("y"),
               py::arg("z"), py::arg("block_identifier"), py::arg("states"),
               py::arg("force") = false,
               py::arg("expected_revision") = py::none());
    module.def("remove", &endstone_sign::remove, py::arg("server"),
               py::arg("dimension"), py::arg("x"), py::arg("y"), py::arg("z"),
               py::arg("force") = false,
               py::arg("expected_revision") = py::none());
    module.def("clone", &endstone_sign::cloneSign, py::arg("server"),
               py::arg("dimension"), py::arg("source_x"),
               py::arg("source_y"), py::arg("source_z"),
               py::arg("destination_x"), py::arg("destination_y"),
               py::arg("destination_z"), py::arg("copy_editor_lock") = false,
               py::arg("force") = false,
               py::arg("expected_source_revision") = py::none());
    module.def("move", &endstone_sign::moveSign, py::arg("server"),
               py::arg("dimension"), py::arg("source_x"),
               py::arg("source_y"), py::arg("source_z"),
               py::arg("destination_x"), py::arg("destination_y"),
               py::arg("destination_z"), py::arg("copy_editor_lock") = false,
               py::arg("force") = false,
               py::arg("expected_source_revision") = py::none());
    module.def("probe_atomic_rejection", &endstone_sign::probeAtomicRejection,
               py::arg("server"), py::arg("dimension"), py::arg("first_x"),
               py::arg("first_y"), py::arg("first_z"),
               py::arg("blocked_x"), py::arg("blocked_y"),
               py::arg("blocked_z"), py::arg("block_identifier"),
               py::arg("states"),
               py::arg("expected_revision") = py::none());
    module.def("probe_api_event_cancellation",
               &endstone_sign::probeApiEventCancellation, py::arg("server"),
               py::arg("dimension"), py::arg("x"), py::arg("y"),
               py::arg("z"), py::arg("expected_revision") = py::none());
    module.def("open_editor", &endstone_sign::openEditor, py::arg("server"),
               py::arg("player"), py::arg("dimension"), py::arg("x"),
               py::arg("y"), py::arg("z"), py::arg("side") = "front",
               py::arg("acquire_lock") = false, py::arg("bypass_wax") = false);
}
