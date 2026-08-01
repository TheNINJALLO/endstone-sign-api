#pragma once

#include "endstone_sign/operations.h"

#include <memory>
#include <optional>
#include <string_view>

namespace endstone {
class Player;
}

namespace endstone_sign {

class SignEventBus;

class ISignAdapter {
public:
    virtual ~ISignAdapter() = default;
    [[nodiscard]] virtual std::string_view name() const noexcept = 0;
    [[nodiscard]] virtual SignCapabilities capabilities() const noexcept = 0;
    [[nodiscard]] virtual std::optional<SignSnapshot> capture(const SignLocation &location) = 0;
    virtual SignApplyResult apply(const SignPatch &patch, bool force) = 0;
    virtual SignApplyResult place(const SignPlaceRequest &request, bool force) = 0;
    virtual SignApplyResult remove(const SignRemoveRequest &request, bool force) = 0;
    virtual SignTransactionResult transact(const SignTransaction &transaction) = 0;
    virtual SignApplyResult openEditor(
        endstone::Player &player,
        const SignOpenEditorRequest &request) = 0;
    virtual void bindEventBus(std::shared_ptr<SignEventBus>) {}
};

} // namespace endstone_sign
