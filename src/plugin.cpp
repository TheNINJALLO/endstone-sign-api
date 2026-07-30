#include "endstone_sign/bds_26_30_adapter.h"
#include "endstone_sign/live_service.h"
#include "endstone_sign/live_probe_service.h"

#include <endstone/endstone.hpp>
#include <endstone/plugin/service_manager.h>
#include <endstone/plugin/service_priority.h>

#include <memory>
#include <string>

#ifndef ENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE
#define ENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE 0
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
        if (!caps.completeControl() && !ENDSTONE_SIGN_EXPERIMENTAL_NATIVE_BRIDGE) {
            const auto report = endstone_sign::inspectBds2630SignActivation(getServer());
            std::string message =
                "Sign API refused to register endstone:sign:v2 because complete native control "
                "is not verified";
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

        if (!caps.completeControl()) {
            getLogger().warning(
                "EXPERIMENTAL TEST BUILD: registering endstone:sign:v2 before native "
                "symbol and disposable-world probe verification; do not use on a production world");
        }

        provider_ = std::make_shared<endstone_sign::LiveSignServiceProvider>(service_);
        probe_provider_ =
            std::make_shared<endstone_sign::LiveSignProbeServiceProvider>(service_);
        getServer().getServiceManager().registerService(
            std::string(endstone_sign::SignServiceName),
            provider_,
            *this,
            endstone::ServicePriority::Normal);
        getServer().getServiceManager().registerService(
            std::string(endstone_sign::SignProbeServiceName),
            probe_provider_,
            *this,
            endstone::ServicePriority::Normal);
        getLogger().info(
            std::string("Sign API ") + ENDSTONE_SIGN_VERSION +
            (caps.completeControl() ? " registered complete service " : " registered experimental service ") +
            std::string(endstone_sign::SignServiceName) +
            " using " + service_->adapterName());
    }

    void onDisable() override {
        getServer().getServiceManager().unregisterAll(*this);
        probe_provider_.reset();
        provider_.reset();
        service_.reset();
        adapter_.reset();
    }

private:
    std::shared_ptr<endstone_sign::ISignAdapter> adapter_;
    std::shared_ptr<endstone_sign::SignService> service_;
    std::shared_ptr<endstone_sign::LiveSignServiceProvider> provider_;
    std::shared_ptr<endstone_sign::LiveSignProbeServiceProvider> probe_provider_;
};

ENDSTONE_PLUGIN("sign_api", ENDSTONE_SIGN_VERSION, SignApiPlugin) {
    prefix = "SignAPI";
    description = "Exact-build complete sign lifecycle API for Endstone";
    website = "https://github.com/TheNINJALLO/endstone-sign-api";
    authors = {"Ninj-OS contributors"};
}
