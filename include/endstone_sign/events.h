#pragma once

#include "endstone_sign/operations.h"

#include <cstddef>
#include <functional>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

namespace endstone_sign {

struct SignActorContext {
    SignMutationOrigin origin{SignMutationOrigin::Unknown};
    std::string actor_name;
    std::string actor_xuid;
    std::string plugin_name;
};

struct SignEvent {
    SignEventKind kind{SignEventKind::BeforeChange};
    SignLocation location;
    SignActorContext actor;
    std::optional<SignSnapshot> before;
    std::optional<SignSnapshot> after;
    bool cancellable{};
    bool cancelled{};
    std::string cancellation_reason;
};

using SignEventListener = std::function<void(SignEvent &)>;

class SignEventBus {
public:
    std::size_t addListener(SignEventListener listener);
    bool removeListener(std::size_t id);
    void publish(SignEvent &event) const;

private:
    struct ListenerEntry {
        std::size_t id{};
        SignEventListener listener;
    };

    mutable std::mutex mutex_;
    std::vector<ListenerEntry> listeners_;
    std::size_t next_id_{1};
};

} // namespace endstone_sign
