#include "endstone_sign/bds_26_30_adapter.h"
#include "endstone_sign/experimental_bds_26_30_adapter.h"

#include "endstone_sign/generated/native_manifest_data.h"
#include "endstone_sign/native_binary_identity.h"

#include <endstone/endstone.hpp>

#include <algorithm>
#include <cctype>
#include <memory>
#include <string>
#include <string_view>
#include <utility>

#ifndef ENDSTONE_SIGN_VERIFIED_NATIVE_BRIDGE
#define ENDSTONE_SIGN_VERIFIED_NATIVE_BRIDGE 0
#endif
#ifndef ENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE
#define ENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE 0
#endif

#ifndef ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE
#define ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE 0
#endif

namespace endstone_sign {
namespace {

std::string_view canonicalBdsBuild(std::string_view build) noexcept {
    if (build.starts_with("1.")) build.remove_prefix(2);
    if (build == "26.33.1") return "26.33";
    return build;
}

bool validIdentifierList(std::string_view value) noexcept {
    if (value.empty() || value.front() == '.' || value.back() == '.') return false;
    bool previous_dot = false;
    for (const char current : value) {
        if (current == '.') {
            if (previous_dot) return false;
            previous_dot = true;
            continue;
        }
        if (!std::isalnum(static_cast<unsigned char>(current)) && current != '-') return false;
        previous_dot = false;
    }
    return true;
}

bool expectedEndstoneVersion(std::string_view runtime) noexcept {
    constexpr std::string_view Expected = "0.11.6";
    if (runtime.starts_with('v')) runtime.remove_prefix(1);
    if (runtime == Expected) return true;
    if (!runtime.starts_with(Expected)) return false;
    auto suffix = runtime.substr(Expected.size());
    if (suffix.starts_with('+')) return validIdentifierList(suffix.substr(1));
    if (suffix.starts_with(".dev")) {
        suffix.remove_prefix(4);
        const auto metadata = suffix.find('+');
        const auto serial = suffix.substr(0, metadata);
        if (serial.empty() || !std::ranges::all_of(serial, [](char c) {
                return c >= '0' && c <= '9';
            })) {
            return false;
        }
        return metadata == std::string_view::npos ||
               validIdentifierList(suffix.substr(metadata + 1));
    }
    return false;
}

class GuardedBds2630SignAdapter final : public ISignAdapter {
public:
    explicit GuardedBds2630SignAdapter(NativeActivationReport report)
        : report_(std::move(report)) {}

    [[nodiscard]] std::string_view name() const noexcept override {
        if (!report_.runtime_version_match || !report_.endstone_version_match)
            return "bds-1.26.33.1-sign-runtime-mismatch";
        if (!report_.executable_hash_match)
            return "bds-1.26.33.1-sign-binary-identity-gate";
        return "bds-1.26.33.1-sign-symbol-gate-closed";
    }

    [[nodiscard]] SignCapabilities capabilities() const noexcept override {
        SignCapabilities caps;
        caps.exact_build_match =
            report_.runtime_version_match && report_.endstone_version_match;
        caps.exact_binary_hash_match = report_.executable_hash_match;
        caps.symbols_validated = report_.symbols_validated;
        caps.stage_probe_passed = report_.stage_probe_passed;
        return caps;
    }

    [[nodiscard]] std::optional<SignSnapshot> capture(const SignLocation &) override {
        return std::nullopt;
    }

    SignApplyResult apply(const SignPatch &, bool) override { return closedResult(); }
    SignApplyResult place(const SignPlaceRequest &, bool) override { return closedResult(); }
    SignApplyResult remove(const SignRemoveRequest &, bool) override { return closedResult(); }

    SignTransactionResult transact(const SignTransaction &) override {
        const auto result = closedResult();
        return {result.status, result.message, {result}, false};
    }

    SignApplyResult openEditor(
        endstone::Player &,
        const SignOpenEditorRequest &) override {
        return closedResult();
    }

private:
    [[nodiscard]] SignApplyResult closedResult() const {
        if (!report_.runtime_version_match || !report_.endstone_version_match) {
            return {
                SignApplyStatus::RuntimeMismatch,
                "Sign API requires BDS 1.26.33.1/26.33 with Endstone 0.11.6",
                0,
            };
        }
        if (!report_.executable_hash_match) {
            return {
                SignApplyStatus::BinaryIdentityMismatch,
                "the running executable does not match the verified Sign API manifest",
                0,
            };
        }
        std::string message = "complete native sign control is disabled";
        if (!report_.failures.empty()) {
            message += ": ";
            for (std::size_t i = 0; i < report_.failures.size(); ++i) {
                if (i != 0) message += ", ";
                message += report_.failures[i];
            }
        }
        return {SignApplyStatus::SymbolValidationFailed, std::move(message), 0};
    }

    NativeActivationReport report_;
};

#if ENDSTONE_SIGN_VERIFIED_NATIVE_BRIDGE
std::shared_ptr<ISignAdapter> makeVerifiedBds2630SignAdapter(endstone::Server &server);
#endif

} // namespace

NativeActivationReport inspectBds2630SignActivation(endstone::Server &server) {
    NativeActivationReport report;
    report.runtime_version_match =
        canonicalBdsBuild(server.getMinecraftVersion()) == "26.33";
    report.endstone_version_match = expectedEndstoneVersion(server.getVersion());
    report.manifest_complete = generated::ManifestComplete;
    report.symbols_validated = generated::SymbolsBehaviorVerified;
    report.stage_probe_passed = generated::DisposableWorldProbePassed;
    report.verified_bridge_compiled = ENDSTONE_SIGN_VERIFIED_NATIVE_BRIDGE != 0;

    if (!generated::ExecutableSha256.empty() && generated::ExecutableSize != 0) {
        const auto identity = inspectCurrentProcessExecutable();
        report.executable_hash_match =
            identity.ok() && identity.size == generated::ExecutableSize &&
            identity.sha256 == generated::ExecutableSha256;
        if (!identity.ok())
            report.failures.emplace_back("runtime executable identity failed: " + identity.error);
    }

    if (!report.runtime_version_match)
        report.failures.emplace_back("BDS runtime version mismatch");
    if (!report.endstone_version_match)
        report.failures.emplace_back("Endstone runtime version mismatch");
    if (!report.manifest_complete)
        report.failures.emplace_back("platform symbol manifest incomplete");
    if (!report.executable_hash_match)
        report.failures.emplace_back("executable SHA-256 mismatch or not activated");
    if (!report.symbols_validated)
        report.failures.emplace_back("symbol signature and behavior validation incomplete");
    if (!report.stage_probe_passed)
        report.failures.emplace_back("disposable-world probe not passed");
    if (!report.verified_bridge_compiled)
        report.failures.emplace_back("verified native bridge not compiled");
    return report;
}

std::shared_ptr<ISignAdapter> makeBds2630SignAdapter(endstone::Server &server) {
    auto report = inspectBds2630SignActivation(server);
#if ENDSTONE_SIGN_VERIFIED_NATIVE_BRIDGE
    if (report.complete()) return makeVerifiedBds2630SignAdapter(server);
#endif
#if ENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE || ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE
    if (report.runtime_version_match && report.endstone_version_match)
        return makeExperimentalBds2630SignAdapter(server);
#endif
    return std::make_shared<GuardedBds2630SignAdapter>(std::move(report));
}

} // namespace endstone_sign
