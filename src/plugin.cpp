#include "endstone_sign/bds_26_30_adapter.h"
#include "endstone_sign/live_service.h"

#include <endstone/endstone.hpp>
#include <endstone/plugin/service_manager.h>
#include <endstone/plugin/service_priority.h>

#include <memory>
#include <string>

#ifndef ENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE
#define ENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE 0
#endif

#ifndef ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE
#define ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE 0
#endif

#ifndef ENDSTONE_SIGN_ACCEPTED_NATIVE_RELEASE
#define ENDSTONE_SIGN_ACCEPTED_NATIVE_RELEASE 0
#endif

class SignApiPlugin : public endstone::Plugin {
public:
    void onEnable() override {
#if ENDSTONE_SIGN_NATIVE_2630
        adapter_ = endstone_sign::makeBds2630SignAdapter(getServer());
#else
        getLogger().error("Sign API package contains no BDS 26.30 native boundary");
        return;
#endif
        service_ = std::make_shared<endstone_sign::SignService>(adapter_);
        const auto caps = service_->capabilities();
        const bool supported_release =
            ENDSTONE_SIGN_SUPPORTED_NATIVE_RELEASE && caps.supportedRelease();
        const bool complete_control = caps.completeControl();
        const bool accepted_release = ENDSTONE_SIGN_ACCEPTED_NATIVE_RELEASE;
        const bool registration_allowed =
            complete_control ||
            (!accepted_release &&
             (supported_release || ENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE));
        if (!registration_allowed) {
            const auto report = endstone_sign::inspectBds2630SignActivation(getServer());
            std::string message =
                accepted_release
                    ? "Production Sign API refused to register endstone:sign:v2 "
                      "because complete native control is unavailable"
                    : "Sign API refused to register endstone:sign:v2 because neither "
                      "the supported tier nor complete native control is available";
            if (!report.failures.empty()) {
                message += ": ";
                for (std::size_t index = 0; index < report.failures.size(); ++index) {
                    if (index != 0) message += ", ";
                    message += report.failures[index];
                }
            }
            getLogger().error(message);
            service_.reset();
            adapter_.reset();
            return;
        }

        if (supported_release) {
            getLogger().info(
                "Registering the production Linux sign service with all native "
                "capability layers enabled");
        } else if (!complete_control) {
            getLogger().warning(
                "EXPERIMENTAL TEST BUILD: registering endstone:sign:v2 before native "
                "symbol and disposable-world probe verification; do not use on a production world");
        }

        provider_ = std::make_shared<endstone_sign::LiveSignServiceProvider>(service_);
        getServer().getServiceManager().registerService(
            std::string(endstone_sign::SignServiceName),
            provider_,
            *this,
            endstone::ServicePriority::Normal);
        getLogger().info(
            std::string("Sign API ") + ENDSTONE_SIGN_VERSION +
            (complete_control ? " registered complete service " :
             supported_release ? " registered supported service " :
                                 " registered experimental service ") +
            std::string(endstone_sign::SignServiceName) +
            " using " + service_->adapterName());
    }

    void onDisable() override {
        getServer().getServiceManager().unregisterAll(*this);
        provider_.reset();
        service_.reset();
        adapter_.reset();
    }

private:
    std::shared_ptr<endstone_sign::ISignAdapter> adapter_;
    std::shared_ptr<endstone_sign::SignService> service_;
    std::shared_ptr<endstone_sign::LiveSignServiceProvider> provider_;
};

ENDSTONE_PLUGIN("sign_api", ENDSTONE_SIGN_VERSION, SignApiPlugin) {
    prefix = "SignAPI";
    description = "Exact-build Linux full-control sign API for Endstone";
    website = "https://github.com/TheNINJALLO/endstone-sign-api";
    authors = {"Ninj-OS contributors"};
}
