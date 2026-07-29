#pragma once

#include "endstone_sign/adapter.h"

#include <map>
#include <mutex>

namespace endstone_sign {

class InMemorySignAdapter final : public ISignAdapter {
public:
    [[nodiscard]] std::string_view name() const noexcept override;
    [[nodiscard]] SignCapabilities capabilities() const noexcept override;
    [[nodiscard]] std::optional<SignSnapshot> capture(const SignLocation &location) override;
    SignApplyResult apply(const SignPatch &patch, bool force) override;
    SignApplyResult place(const SignPlaceRequest &request, bool force) override;
    SignApplyResult remove(const SignRemoveRequest &request, bool force) override;
    SignTransactionResult transact(const SignTransaction &transaction) override;
    SignApplyResult openEditor(
        endstone::Player &player,
        const SignOpenEditorRequest &request) override;

    void upsert(SignSnapshot snapshot);
    bool erase(const SignLocation &location);
    [[nodiscard]] std::size_t size() const;

private:
    using SignMap = std::map<SignLocation, SignSnapshot>;
    static SignApplyResult applyTo(SignMap &signs, const SignPatch &patch, bool force);
    static SignApplyResult placeInto(SignMap &signs, const SignPlaceRequest &request, bool force);
    static SignApplyResult removeFrom(SignMap &signs, const SignRemoveRequest &request, bool force);

    mutable std::mutex mutex_;
    SignMap signs_;
};

} // namespace endstone_sign
