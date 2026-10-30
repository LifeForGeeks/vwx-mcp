#pragma once
#include "VWFC/PluginSupport/VWExtensionVSFunctions.h"

namespace VwxBridge {
class CExtVMNativeFunctions : public VWFC::PluginSupport::VWExtensionVSFunctions {
    DEFINE_VWVSFunctions;
public:
    CExtVMNativeFunctions(CallBackPtr cbp);
    virtual ~CExtVMNativeFunctions() = default;
};
}
