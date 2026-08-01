#undef ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION
#define ENDSTONE_SIGN_VERIFIED_NATIVE_IMPLEMENTATION 1
#include "experimental_bds_26_30_adapter.cpp"

namespace endstone_sign {

std::shared_ptr<ISignAdapter> makeVerifiedBds2630SignAdapter(
    endstone::Server &server) {
    return std::make_shared<ExperimentalBds2630SignAdapter>(server);
}

} // namespace endstone_sign
