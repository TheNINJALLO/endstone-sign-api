#pragma once

#include "endstone_sign/service.h"

#include <endstone/plugin/service.h>

#include <atomic>
#include <cstdint>
#include <memory>
#include <optional>
#include <string_view>
#include <utility>

namespace endstone_sign {

inline constexpr std::string_view SignProbeServiceName =
    "endstone:sign:probe:v1";

struct SignApiCancellationProbeResult {
    SignApplyResult apply_result;
    bool event_observed{};
    bool event_cancelled{};
    bool state_unchanged{};
    bool listener_removed{};

    [[nodiscard]] bool ok() const noexcept {
        return apply_result.status == SignApplyStatus::Cancelled &&
               event_observed && event_cancelled && state_unchanged &&
               listener_removed;
    }
};

class LiveSignProbeService : public endstone::Service {
public:
    ~LiveSignProbeService() override = default;
    virtual SignApiCancellationProbeResult probeApiEventCancellation(
        const SignLocation &location,
        std::optional<std::uint64_t> expected_revision) = 0;
};

class LiveSignProbeServiceProvider final : public LiveSignProbeService {
public:
    explicit LiveSignProbeServiceProvider(std::shared_ptr<SignService> service)
        : service_(std::move(service)) {}

    SignApiCancellationProbeResult probeApiEventCancellation(
        const SignLocation &location,
        std::optional<std::uint64_t> expected_revision) override;

private:
    std::shared_ptr<SignService> service_;
    std::atomic<std::uint64_t> next_probe_id_{1};
};

} // namespace endstone_sign
