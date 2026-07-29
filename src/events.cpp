#include "endstone_sign/events.h"

#include <algorithm>
#include <stdexcept>
#include <utility>

namespace endstone_sign {

std::size_t SignEventBus::addListener(SignEventListener listener) {
    if (!listener) throw std::invalid_argument("sign event listener must not be empty");
    std::scoped_lock lock(mutex_);
    const auto id = next_id_++;
    listeners_.push_back({id, std::move(listener)});
    return id;
}

bool SignEventBus::removeListener(std::size_t id) {
    std::scoped_lock lock(mutex_);
    const auto old_size = listeners_.size();
    std::erase_if(listeners_, [id](const ListenerEntry &entry) { return entry.id == id; });
    return listeners_.size() != old_size;
}

void SignEventBus::publish(SignEvent &event) const {
    std::vector<ListenerEntry> listeners;
    {
        std::scoped_lock lock(mutex_);
        listeners = listeners_;
    }
    for (const auto &entry : listeners) {
        entry.listener(event);
        if (event.cancellable && event.cancelled) break;
    }
}

} // namespace endstone_sign
