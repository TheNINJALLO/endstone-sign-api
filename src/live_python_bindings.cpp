#include "endstone_sign/live_service.h"

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
#include <string>
#include <vector>

namespace py = pybind11;

namespace endstone_sign {
namespace {

std::shared_ptr<LiveSignService> loadService(endstone::Server &server) {
    return server.getServiceManager().load<LiveSignService>(std::string(SignServiceName));
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
    module.doc() = "Experimental live bridge to endstone:sign:v2";
    module.attr("__version__") = "0.2.0a6";
    module.def("available", &endstone_sign::available, py::arg("server"));
    module.def("status", &endstone_sign::status, py::arg("server"));
    module.def("capture", &endstone_sign::capture, py::arg("server"),
               py::arg("dimension"), py::arg("x"), py::arg("y"), py::arg("z"));
    module.def("set_text", &endstone_sign::setText, py::arg("server"),
               py::arg("dimension"), py::arg("x"), py::arg("y"), py::arg("z"),
               py::arg("side"), py::arg("lines"), py::arg("argb") = py::none(),
               py::arg("glowing") = py::none(), py::arg("waxed") = py::none(),
               py::arg("force") = false,
               py::arg("expected_revision") = py::none());
    module.def("place", &endstone_sign::place, py::arg("server"),
               py::arg("dimension"), py::arg("x"), py::arg("y"), py::arg("z"),
               py::arg("block_identifier"), py::arg("states"));
    module.def("remove", &endstone_sign::remove, py::arg("server"),
               py::arg("dimension"), py::arg("x"), py::arg("y"), py::arg("z"),
               py::arg("force") = false,
               py::arg("expected_revision") = py::none());
    module.def("open_editor", &endstone_sign::openEditor, py::arg("server"),
               py::arg("player"), py::arg("dimension"), py::arg("x"),
               py::arg("y"), py::arg("z"), py::arg("side") = "front",
               py::arg("acquire_lock") = false, py::arg("bypass_wax") = false);
}
