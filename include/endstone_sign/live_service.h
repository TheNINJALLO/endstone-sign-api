#pragma once

#include "endstone_sign/service.h"

#include <endstone/plugin/service.h>

#include <cstdint>
#include <memory>
#include <string_view>

namespace endstone_sign {

inline constexpr std::uint32_t SignServiceAbiVersion = 2;
inline constexpr std::string_view SignServiceName = "endstone:sign:v2";

class LiveSignService : public endstone::Service {
public:
    ~LiveSignService() override = default;
    [[nodiscard]] virtual std::optional<SignSnapshot> capture(const SignLocation &location) = 0;
    virtual SignApplyResult apply(const SignPatch &patch, bool force = false) = 0;
    virtual SignApplyResult place(const SignPlaceRequest &request, bool force = false) = 0;
    virtual SignApplyResult remove(const SignRemoveRequest &request, bool force = false) = 0;
    virtual SignApplyResult cloneSign(const SignCloneRequest &request, bool force = false) = 0;
    virtual SignApplyResult moveSign(const SignMoveRequest &request, bool force = false) = 0;
    virtual SignTransactionResult transact(const SignTransaction &transaction) = 0;
    virtual SignApplyResult openEditor(
        endstone::Player &player,
        const SignOpenEditorRequest &request) = 0;
    [[nodiscard]] virtual SignCapabilities capabilities() const noexcept = 0;
    [[nodiscard]] virtual std::string adapterName() const = 0;
};

class LiveSignServiceProvider final : public LiveSignService {
public:
    explicit LiveSignServiceProvider(std::shared_ptr<SignService> service)
        : service_(std::move(service)) {}

    [[nodiscard]] std::optional<SignSnapshot> capture(const SignLocation &location) override {
        return service_->capture(location);
    }
    SignApplyResult apply(const SignPatch &patch, bool force) override {
        return service_->apply(patch, force);
    }
    SignApplyResult place(const SignPlaceRequest &request, bool force) override {
        return service_->place(request, force);
    }
    SignApplyResult remove(const SignRemoveRequest &request, bool force) override {
        return service_->remove(request, force);
    }
    SignApplyResult cloneSign(const SignCloneRequest &request, bool force) override {
        return service_->cloneSign(request, force);
    }
    SignApplyResult moveSign(const SignMoveRequest &request, bool force) override {
        return service_->moveSign(request, force);
    }
    SignTransactionResult transact(const SignTransaction &transaction) override {
        return service_->transact(transaction);
    }
    SignApplyResult openEditor(
        endstone::Player &player,
        const SignOpenEditorRequest &request) override {
        return service_->openEditor(player, request);
    }
    [[nodiscard]] SignCapabilities capabilities() const noexcept override {
        return service_->capabilities();
    }
    [[nodiscard]] std::string adapterName() const override {
        return service_->adapterName();
    }

private:
    std::shared_ptr<SignService> service_;
};

} // namespace endstone_sign
