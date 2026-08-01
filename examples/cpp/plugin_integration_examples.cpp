#include "endstone_sign/live_service.h"

#include <endstone/plugin/service_manager.h>
#include <endstone/server.h>

#include <algorithm>
#include <cstdint>
#include <memory>
#include <sstream>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace sign_examples {

using endstone_sign::LiveSignService;
using endstone_sign::SignEvent;
using endstone_sign::SignEventKind;
using endstone_sign::SignLines;
using endstone_sign::SignLocation;
using endstone_sign::SignPatch;
using endstone_sign::SignTextPatch;

std::shared_ptr<LiveSignService> loadSupportedSignApi(endstone::Server &server) {
    auto signs = server.getServiceManager().load<LiveSignService>(
        std::string(endstone_sign::SignServiceName));
    if (!signs || !signs->capabilities().supportedRelease()) return {};
    return signs;
}

std::string shortLine(std::string value) {
    // These examples use ASCII display strings. Production plugins should
    // truncate on UTF-8 code-point boundaries and honor their server font/UI.
    constexpr std::size_t ExampleLineLimit = 22;
    if (value.size() > ExampleLineLimit) value.resize(ExampleLineLimit);
    return value;
}

bool writeFront(
    const std::shared_ptr<LiveSignService> &signs,
    const SignLocation &location,
    SignLines lines) {
    if (!signs) return false;
    const auto caps = signs->capabilities();
    if (!caps.capture || !caps.read_text || !caps.write_text ||
        !caps.front_and_back || !caps.client_updates) {
        return false;
    }

    const auto current = signs->capture(location);
    if (!current) return false;

    SignPatch patch;
    patch.location = location;
    patch.expected_revision = current->revision;
    patch.front.emplace();
    patch.front->lines = std::move(lines);
    patch.send_client_update = true;
    patch.persist = true;
    return signs->apply(patch).ok();
}

// Example 1: call this after the linked chest inventory or shop price changes.
bool refreshChestShopSign(
    const std::shared_ptr<LiveSignService> &signs,
    const SignLocation &sign,
    std::string item_name,
    const std::int32_t stock,
    const std::int32_t price_each) {
    return writeFront(signs, sign, {
        "[CHEST SHOP]",
        shortLine(std::move(item_name)),
        shortLine("$" + std::to_string(price_each) + " each"),
        shortLine("Stock: " + std::to_string(std::max(stock, 0))),
    });
}

// Supply an implementation backed by your Discord library or webhook queue.
// enqueueSignUpdate must return quickly because Sign API events run on the
// Endstone primary thread.
class DiscordSink {
public:
    virtual ~DiscordSink() = default;
    virtual void enqueueSignUpdate(
        const SignLocation &location,
        const SignLines &front,
        std::string_view source_plugin) = 0;
};

// Example 2a: mirror successful Sign API changes to Discord.
std::size_t installDiscordMirror(
    const std::shared_ptr<LiveSignService> &signs,
    DiscordSink &discord) {
    if (!signs || !signs->capabilities().api_edit_events) return 0;
    return signs->addEventListener([&discord](SignEvent &event) {
        if ((event.kind != SignEventKind::AfterChange &&
             event.kind != SignEventKind::AfterPlace) ||
            !event.after) {
            return;
        }
        discord.enqueueSignUpdate(
            event.location,
            event.after->front.lines,
            event.actor.plugin_name);
    });
}

// Example 2b: schedule this function onto Endstone's primary thread from your
// Discord callback. Never invoke the Sign API directly on the Discord thread.
bool applyDiscordPostOnServerThread(
    const std::shared_ptr<LiveSignService> &signs,
    const SignLocation &sign,
    std::string author,
    std::string message) {
    return writeFront(signs, sign, {
        "[DISCORD]",
        shortLine(std::move(author)),
        shortLine(std::move(message)),
        "",
    });
}

// Example 3: call tick() from an Endstone scheduler task. Each call captures a
// fresh revision, so a player/plugin edit causes a safe conflict or becomes the
// base for the next frame instead of being silently overwritten.
class MovingSignMessage {
public:
    MovingSignMessage(
        std::shared_ptr<LiveSignService> signs,
        SignLocation sign,
        std::vector<std::string> frames)
        : signs_(std::move(signs)), sign_(std::move(sign)), frames_(std::move(frames)) {}

    bool tick() {
        if (frames_.empty()) return false;
        const auto &frame = frames_[next_frame_++ % frames_.size()];
        return writeFront(signs_, sign_, {
            "[SERVER NEWS]",
            shortLine(frame),
            shortLine("Frame " + std::to_string(next_frame_)),
            "",
        });
    }

private:
    std::shared_ptr<LiveSignService> signs_;
    SignLocation sign_;
    std::vector<std::string> frames_;
    std::size_t next_frame_{};
};

} // namespace sign_examples
