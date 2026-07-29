#pragma once

#include "endstone_sign/adapter.h"
#include "endstone_sign/events.h"

#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace endstone_sign {

class SignService {
public:
    explicit SignService(
        std::shared_ptr<ISignAdapter> adapter,
        SignValidationLimits limits = {},
        std::shared_ptr<SignEventBus> event_bus = {});

    [[nodiscard]] std::optional<SignSnapshot> capture(const SignLocation &location);
    SignApplyResult apply(
        const SignPatch &patch,
        bool force = false,
        SignActorContext actor = {});
    SignApplyResult place(
        const SignPlaceRequest &request,
        bool force = false,
        SignActorContext actor = {});
    SignApplyResult remove(
        const SignRemoveRequest &request,
        bool force = false,
        SignActorContext actor = {});
    SignApplyResult cloneSign(
        const SignCloneRequest &request,
        bool force = false,
        SignActorContext actor = {});
    SignApplyResult moveSign(
        const SignMoveRequest &request,
        bool force = false,
        SignActorContext actor = {});
    SignTransactionResult transact(
        const SignTransaction &transaction,
        SignActorContext actor = {});
    SignApplyResult openEditor(
        endstone::Player &player,
        const SignOpenEditorRequest &request,
        SignActorContext actor = {});

    [[nodiscard]] SignCapabilities capabilities() const noexcept;
    [[nodiscard]] std::string adapterName() const;
    [[nodiscard]] std::shared_ptr<SignEventBus> eventBus() const noexcept { return event_bus_; }

private:
    struct PreparedEvent {
        SignEventKind before_kind{};
        SignEventKind after_kind{};
        SignLocation location;
        SignActorContext actor;
        std::optional<SignSnapshot> before;
        std::optional<SignSnapshot> expected_after;
    };

    [[nodiscard]] std::optional<std::string> validateLocation(
        const SignLocation &location) const;
    [[nodiscard]] std::optional<std::string> validatePlacement(
        const SignPlaceRequest &request) const;
    [[nodiscard]] std::optional<std::string> validatePatch(
        const SignPatch &patch,
        const SignSnapshot &current) const;
    [[nodiscard]] std::optional<SignApplyResult> prepareTransactionEvents(
        const SignTransaction &transaction,
        const SignActorContext &actor,
        std::vector<PreparedEvent> &events);
    bool publishBefore(
        SignEventKind kind,
        const SignLocation &location,
        const SignActorContext &actor,
        std::optional<SignSnapshot> before,
        std::optional<SignSnapshot> after,
        std::string &reason) const;
    void publishAfter(
        SignEventKind kind,
        const SignLocation &location,
        const SignActorContext &actor,
        std::optional<SignSnapshot> before,
        std::optional<SignSnapshot> after) const;

    std::shared_ptr<ISignAdapter> adapter_;
    SignValidationLimits limits_;
    std::shared_ptr<SignEventBus> event_bus_;
};

} // namespace endstone_sign
