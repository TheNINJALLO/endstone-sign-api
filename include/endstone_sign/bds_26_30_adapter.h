#pragma once

#include "endstone_sign/adapter.h"

#include <memory>
#include <string>
#include <vector>

namespace endstone {
class Server;
}

namespace endstone_sign {

struct NativeActivationReport {
    bool runtime_version_match{};
    bool endstone_version_match{};
    bool executable_hash_match{};
    bool manifest_complete{};
    bool symbols_validated{};
    bool stage_probe_passed{};
    bool verified_bridge_compiled{};
    std::vector<std::string> failures;

    [[nodiscard]] bool complete() const noexcept {
        return runtime_version_match && endstone_version_match && executable_hash_match &&
               manifest_complete && symbols_validated && stage_probe_passed &&
               verified_bridge_compiled && failures.empty();
    }
};

// Returns a guarded exact-build adapter. It remains fail-closed until the
// generated platform manifest and stage probe are complete. No guessed offsets
// or partial capability service is ever exposed.
std::shared_ptr<ISignAdapter> makeBds2630SignAdapter(endstone::Server &server);
[[nodiscard]] NativeActivationReport inspectBds2630SignActivation(endstone::Server &server);

} // namespace endstone_sign
