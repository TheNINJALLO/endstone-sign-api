#include "endstone_sign/live_probe_service.h"

#include <atomic>
#include <memory>
#include <string>

namespace endstone_sign {

SignApiCancellationProbeResult
LiveSignProbeServiceProvider::probeApiEventCancellation(
    const SignLocation &location,
    std::optional<std::uint64_t> expected_revision) {
    const auto before = service_->capture(location);
    if (!before) {
        return {
            {SignApplyStatus::NotASign,
             "API cancellation probe target is not a sign", 0},
            false,
            false,
            false,
            false,
        };
    }
    if (expected_revision && *expected_revision != before->revision) {
        return {
            {SignApplyStatus::Conflict, "API cancellation probe revision changed",
             before->revision},
            false,
            false,
            false,
            false,
        };
    }

    struct ListenerState {
        SignLocation location;
        std::uint64_t before_revision{};
        bool desired_persist_formatting{};
        std::string actor_token;
        std::atomic<bool> active{true};
        std::atomic<bool> observed{false};
    };
    auto state = std::make_shared<ListenerState>();
    state->location = location;
    state->before_revision = before->revision;
    state->desired_persist_formatting = !before->front.persist_formatting;
    const auto probe_id = next_probe_id_.fetch_add(1, std::memory_order_relaxed);
    state->actor_token = "alpha7-api-cancel-" +
                         std::to_string(before->revision) + "-" +
                         std::to_string(probe_id);

    const auto bus = service_->eventBus();
    const auto listener_id = bus->addListener([state](SignEvent &event) {
        if (!state->active.load(std::memory_order_acquire) ||
            event.kind != SignEventKind::BeforeChange ||
            event.location != state->location || !event.cancellable ||
            event.actor.plugin_name != "endstone_sign_alpha7_probe" ||
            event.actor.actor_name != state->actor_token || !event.before ||
            !event.after ||
            event.before->revision != state->before_revision ||
            event.after->front.persist_formatting !=
                state->desired_persist_formatting) {
            return;
        }
        state->observed.store(true, std::memory_order_release);
        event.cancelled = true;
        event.cancellation_reason = "alpha7 API cancellation probe";
    });

    SignApplyResult apply_result;
    try {
        SignPatch patch;
        patch.location = location;
        patch.expected_revision = before->revision;
        SignTextPatch text;
        text.persist_formatting = state->desired_persist_formatting;
        patch.front = std::move(text);
        SignActorContext actor;
        actor.origin = SignMutationOrigin::Api;
        actor.plugin_name = "endstone_sign_alpha7_probe";
        actor.actor_name = state->actor_token;
        apply_result = service_->apply(patch, false, std::move(actor));
    } catch (...) {
        state->active.store(false, std::memory_order_release);
        bus->removeListener(listener_id);
        throw;
    }

    state->active.store(false, std::memory_order_release);
    const bool listener_removed = bus->removeListener(listener_id);
    const auto after = service_->capture(location);
    const bool unchanged = after && after->revision == before->revision;
    const bool observed = state->observed.load(std::memory_order_acquire);
    return {
        apply_result,
        observed,
        observed && apply_result.status == SignApplyStatus::Cancelled,
        unchanged,
        listener_removed,
    };
}

} // namespace endstone_sign
