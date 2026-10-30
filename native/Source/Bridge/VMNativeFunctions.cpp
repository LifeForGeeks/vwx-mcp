#include "StdAfx.h"
#include "VMNativeFunctions.h"
#include "Interfaces/VectorWorks/Extension/IViewportVisualizationOverride.h"
#include "Interfaces/VectorWorks/Extension/ICableConnectionsProvider.h"
#include "Interfaces/VectorWorks/Filing/IImportExportGDTF.h"
#include <cmath>
#include <filesystem>
#include <set>

using namespace VWFC::PluginSupport;
using namespace VectorWorks::Extension;
using namespace VectorWorks::Extension::ViewportVisializationOverride;
using nlohmann::json;

namespace {
// Output-only dynamic array avoids the short VectorScript STRING limit.
const SFunctionDef functions[] = {
    {"VMGetViewportContext", "Velvet Mirror", "Read native viewport style and data-visualization context as JSON.",
     3100, kVLIBScopeUniversal, false,
     {{"viewport", kHandleArgType}, {"resultJSON", kCharDynarrayVarArgType}, {nullptr, 0}}},
    {"VMGetElectricalComponents", "Velvet Mirror", "Read native electrical components and internal links as JSON; does not create connections.",
     3100, kVLIBScopeUniversal, false,
     {{"object", kHandleArgType}, {"resultJSON", kCharDynarrayVarArgType}, {nullptr, 0}}},
    {"VMExportSymbolLibrary", "Velvet Mirror", "Export selected symbol definitions to a new native library file; refuses existing destinations.",
     3100, kVLIBScopeUniversal, false,
     {{"requestJSON", kCharDynarrayArgType}, {"resultJSON", kCharDynarrayVarArgType}, {nullptr, 0}}},
    {"VMCableLifecycleProbe", "Velvet Mirror", "Experimental guarded native cable creation/style update; requires independent post-event verification.",
     3100, kVLIBScopeUniversal, false,
     {{"requestJSON", kCharDynarrayArgType}, {"resultJSON", kCharDynarrayVarArgType}, {nullptr, 0}}},
    {"VMGDTFExchange", "Velvet Mirror", "Import an explicit GDTF mode onto a native Lighting Device, or export its GDTF; guarded document and files.",
     3100, kVLIBScopeUniversal, false,
     {{"requestJSON", kCharDynarrayArgType}, {"resultJSON", kCharDynarrayVarArgType}, {nullptr, 0}}},
    {nullptr}
};

class DataVisScope {
    IAttrByDataOverride* service;
public:
    DataVisScope(IAttrByDataOverride* s, MCObjectHandle viewport) : service(s) { service->AddContext(viewport); }
    ~DataVisScope() { service->RemoveContext(); }
    DataVisScope(const DataVisScope&) = delete;
    DataVisScope& operator=(const DataVisScope&) = delete;
};

std::string BoundedText(const TXString& value) {
    std::string text(value.GetCharPtr());
    if (text.size() > 2048) throw std::runtime_error("Electrical provider string exceeds 2048 bytes");
    return text;
}

std::string ElectricalIdentity(const UuidStorage& value) {
    return value.IsEmpty() ? std::string() : BoundedText(value.ToString());
}

json ReadElectricalComponents(MCObjectHandle object) {
    json result = {{"contract_version", 1}, {"status", "error"}};
    try {
        if (!object || gSDK->GetObjectTypeN(object) != 86)
            throw std::runtime_error("A native parametric object handle is required");
        TXString uuid;
        if (!gSDK->GetObjectUuid(object, uuid)) throw std::runtime_error("Object UUID unavailable");
        result["object_id"] = BoundedText(uuid);
        VCOMSinkPtr<ICableConnectionsProvider> provider(object, IID_CableConnectionsProvider);
        result["provider_available"] = bool(provider);
        json components = json::array();
        if (provider) {
            TElectricComponentArray native;
            auto error = provider->GetObjectConnections(object, native);
            result["provider_status_code"] = static_cast<Sint32>(error);
            if (error != kVCOMError_NoError) throw std::runtime_error("GetObjectConnections returned a failure code");
            if (native.size() > 512) throw std::runtime_error("Electrical provider exceeds 512 components");
            size_t linkCount = 0;
            for (const auto& c : native) {
                // Unused SDK fVoltage/fMaximumPower are deliberately not exposed as engineering values.
                if (!std::isfinite(c.fAverageConsumption) || !std::isfinite(c.fMaximumConsumption))
                    throw std::runtime_error("Electrical provider returned non-finite consumption");
                if (c.fInternalConnections.size() > 2048 - linkCount)
                    throw std::runtime_error("Electrical provider exceeds 2048 internal connections");
                linkCount += c.fInternalConnections.size();
                json links = json::array();
                for (const auto& link : c.fInternalConnections) {
                    links.push_back({{"name", BoundedText(link.fName)}, {"own_socket", link.fOwnSocket},
                        {"other_socket", link.fOtherSocketSocket},
                        {"other_component_id", ElectricalIdentity(link.fOtherComponent)}});
                }
                components.push_back({{"device_id", ElectricalIdentity(c.fDeviceUUID)},
                    {"component_id", ElectricalIdentity(c.fCompGeometryUID)},
                    {"type_code", static_cast<int>(c.fType)}, {"name", BoundedText(c.fName)},
                    {"connector", BoundedText(c.fPowerConnector)},
                    {"average_consumption_w", c.fAverageConsumption}, {"maximum_consumption_w", c.fMaximumConsumption},
                    {"is_virtual", c.fIsDefaultComponent}, {"is_link_through", c.fIsLinkThroughOutput},
                    {"internal_connections", links}});
            }
        }
        result["components"] = components;
        result["status"] = "ok";
        if (result.dump().size() > 1000000) throw std::runtime_error("Electrical provider JSON exceeds 1 MB");
    }
    catch (const std::exception& error) {
        result.erase("components"); result["status"] = "error"; result["error"] = error.what();
    }
    catch (...) {
        result.erase("components"); result["status"] = "error"; result["error"] = "Unknown native electrical provider failure";
    }
    return result;
}

json ExportSymbolLibrary(const TXString& requestText) {
    namespace fs = std::filesystem;
    using namespace VectorWorks::Filing;
    json result = {{"contract_version",1},{"status","error"},{"retry_safe",true}};
    try {
        std::string text(requestText.GetCharPtr());
        if (text.size()>16384) throw std::runtime_error("Request exceeds 16 KB");
        auto request=json::parse(text);
        if (!request.is_object() || request.size()<3 || request.size()>4 || (request.size()==4 && !request.contains("allow_empty_existing")) || !request.contains("expected_document") || !request.contains("path") || !request.contains("object_ids"))
            throw std::runtime_error("Expected document, path and object_ids only");
        auto expected=fs::u8path(request.at("expected_document").get<std::string>());
        auto path=fs::u8path(request.at("path").get<std::string>());
        if (!expected.is_absolute() || !path.is_absolute() || path.extension()!=L".vwx" || !fs::is_directory(path.parent_path()))
            throw std::runtime_error("Absolute document and .vwx destination with existing parent required");
        bool emptyExisting=request.value("allow_empty_existing",false);
        if (fs::exists(path) && !emptyExisting) throw std::runtime_error("Destination already exists; explicit empty-library mode required");
        if (emptyExisting && !fs::is_regular_file(path)) throw std::runtime_error("Existing empty library required");
        IFileIdentifierPtr active; bool saved=false; TXString activePath;
        if (!gSDK->GetActiveDocument(&active,saved) || !active || !saved || active->GetFileFullPath(activePath)!=kVCOMError_NoError)
            throw std::runtime_error("Saved active document required");
        auto actual=fs::weakly_canonical(fs::u8path(activePath.GetCharPtr()));
        if (_wcsicmp(actual.c_str(),fs::weakly_canonical(expected).c_str())!=0)
            throw std::runtime_error("Active document guard mismatch");
        if (_wcsicmp(actual.c_str(),fs::weakly_canonical(path).c_str())==0)
            throw std::runtime_error("Cannot export into the active drawing");
        auto ids=request.at("object_ids");
        if (!ids.is_array() || ids.empty() || ids.size()>25) throw std::runtime_error("Expected 1..25 symbol UUIDs");
        std::set<MCObjectHandle> seen;
        VectorWorks::TVWArray_MCObjectHandle symbols;
        json names=json::array();
        for (const auto& id:ids) {
            auto uuid=id.get<std::string>();
            if (uuid.empty() || uuid.size()>128) throw std::runtime_error("Invalid symbol UUID");
            auto h=gSDK->GetObjectByUuid(TXString(uuid.c_str()));
            if (!h || gSDK->GetObjectTypeN(h)!=16 || !seen.insert(h).second)
                throw std::runtime_error("Expected unique symbol definitions");
            symbols.Append(h); TXString name; gSDK->GetObjectName(h,name); names.push_back(name.GetCharPtr());
        }
        IFileIdentifierPtr target(IID_FileIdentifier);
        if (!target || target->Set(TXString(path.u8string().c_str()))!=kVCOMError_NoError)
            throw std::runtime_error("Cannot identify destination file");
        if (emptyExisting) {
            VectorWorks::TVWArray_OpenFileInformation openFiles;
            gSDK->GetOpenFilesList(openFiles);
            for (size_t index=0; index<openFiles.GetSize(); ++index) {
                TXString openPath;
                if (!openFiles[index].fIsInMemoryOnly && openFiles[index].fpFileID &&
                    openFiles[index].fpFileID->GetFileFullPath(openPath)==kVCOMError_NoError &&
                    _wcsicmp(fs::weakly_canonical(fs::u8path(openPath.GetCharPtr())).c_str(),fs::weakly_canonical(path).c_str())==0)
                    throw std::runtime_error("Close the destination library before exporting resources into it");
            }
            for (short type : {short(16),short(47)}) {
                Sint32 count=0;
                auto list=gSDK->BuildResourceListN(type,target,count);
                gSDK->DisposeResourceList(list);
                if (count!=0) throw std::runtime_error("Destination already contains symbols or record formats");
            }
        }
        // SDK owns resource dependency export. Never serialize VWX or copy the whole QA drawing.
        result["retry_safe"]=false;
        bool ok=gSDK->ExportResourceList(symbols,target,true,false);
        result["sdk_result"]=ok;
        result["path"]=path.u8string(); result["symbol_names"]=names; result["object_ids"]=ids;
        result["file_exists"]=fs::exists(path);
        result["file_bytes"]=fs::exists(path) ? fs::file_size(path) : 0;
        if (!ok || !fs::exists(path) || fs::file_size(path)==0)
            throw std::runtime_error("SDK did not produce a confirmed library; inspect destination before retrying");
        result["status"]="ok";
        result["resource_readback_verified"]=false;
        result["native_catalog_registered"]=false;
    }
    catch (const std::exception& error) { result["error"]=error.what(); }
    catch (...) { result["error"]="Unknown native symbol export failure"; }
    return result;
}

// This is an investigation adapter, not a certified cable creator. Keep all mutation
// outcomes in the receipt, including failures after creation; never auto-delete/retry.
json ProbeCableLifecycle(const TXString& requestText) {
    namespace fs = std::filesystem;
    using namespace VectorWorks::Filing;
    using VWFC::VWObjects::VWParametricObj;
    json result={{"contract_version",1},{"status","error"},{"experimental",true},
        {"retry_safe",true},{"requires_verification",true}};
    MCObjectHandle cable=nullptr;
    try {
        std::string text(requestText.GetCharPtr());
        if (text.size()>8192) throw std::runtime_error("Request exceeds 8 KB");
        auto request=json::parse(text);
        if (!request.is_object() || !request.contains("operation") || !request.contains("expected_document"))
            throw std::runtime_error("Operation and expected_document required");
        auto operation=request.at("operation").get<std::string>();
        bool create=operation=="create_styled";
        if (!create && operation!="update_style") throw std::runtime_error("Unknown lifecycle operation");
        std::set<std::string> allowed={"operation","expected_document"};
        if (create) { allowed.insert("path_id"); allowed.insert("style_id"); }
        else allowed.insert("object_id");
        if (request.size()!=allowed.size()) throw std::runtime_error("Incorrect request fields");
        for (auto it=request.begin(); it!=request.end(); ++it)
            if (!allowed.count(it.key()) || !it.value().is_string()) throw std::runtime_error("Expected named string fields only");
        auto expected=fs::u8path(request.at("expected_document").get<std::string>());
        if (!expected.is_absolute()) throw std::runtime_error("Absolute expected document required");
        IFileIdentifierPtr active; bool saved=false; TXString activePath;
        if (!gSDK->GetActiveDocument(&active,saved) || !active || !saved || active->GetFileFullPath(activePath)!=kVCOMError_NoError)
            throw std::runtime_error("Saved active document required");
        if (_wcsicmp(fs::weakly_canonical(fs::u8path(activePath.GetCharPtr())).c_str(),fs::weakly_canonical(expected).c_str())!=0)
            throw std::runtime_error("Active document guard mismatch");
        auto resolve=[&](const char* key,short type) {
            auto id=request.at(key).get<std::string>();
            if (id.empty() || id.size()>128) throw std::runtime_error("Invalid object UUID");
            auto h=gSDK->GetObjectByUuid(TXString(id.c_str()));
            if (!h || gSDK->GetObjectTypeN(h)!=type) throw std::runtime_error("Object missing or wrong native type");
            return h;
        };
        MCObjectHandle style=nullptr,path=nullptr;
        if (create) {
            path=resolve("path_id",111); style=resolve("style_id",16);
            if (gSDK->ParentObject(path)!=gSDK->GetActiveLayer()) throw std::runtime_error("Path must be a top-level active-layer object");
            auto pieces=gSDK->NurbsCurveGetNumPieces(path);
            if (pieces<1 || pieces>199) throw std::runtime_error("Expected 1..199 linear NURBS pieces");
            for (Sint32 i=0;i<pieces;++i)
                if (gSDK->NurbsDegree(path,i)!=1 || gSDK->NurbsGetNumPts(path,i)!=2)
                    throw std::runtime_error("Probe accepts degree-one two-point pieces only");
        } else {
            cable=resolve("object_id",86);
            if (gSDK->ParentObject(cable)!=gSDK->GetActiveLayer()) throw std::runtime_error("Cable must be on the active layer");
            VWParametricObj object(cable);
            if (object.GetParametricName()!="CableObject") throw std::runtime_error("Expected CableObject");
            for (auto key:{"StartObjectUUID","EndObjectUUID","__StartConnectorUUID","__EndConnectorUUID"})
                if (!object.GetParamString(key).IsEmpty()) throw std::runtime_error("Only cables with blank endpoint/component references are supported");
            style=object.GetStyleHandle();
        }
        if (!style || !gSDK->IsPluginStyle(style)) throw std::runtime_error("Native cable style required");
        size_t children=0,cables=0;
        for(auto child=gSDK->FirstMemberObj(style);child;child=gSDK->NextObject(child)) {
            if (++children>256) throw std::runtime_error("Style child limit exceeded");
            if (gSDK->GetObjectTypeN(child)==86 && VWParametricObj(child).GetParametricName()=="CableObject") {
                ++cables;
                VWParametricObj definition(child);
                for (auto key:{"StartObjectUUID","EndObjectUUID","__StartConnectorUUID","__EndConnectorUUID"})
                    if (!definition.GetParamString(key).IsEmpty()) throw std::runtime_error("Style definition has endpoint references");
            }
        }
        if (cables!=1) throw std::runtime_error("Style must contain exactly one CableObject");
        result["operation"]=operation;
        result["retry_safe"]=false;
        if (create) {
            auto classIndex=gSDK->GetObjectClass(path);
            // Unlike the scripting wrapper, the SDK exposes doRegen=false.
            cable=gSDK->CreateCustomObjectPath("CableObject",path,nullptr,false);
            if (!cable || gSDK->GetObjectTypeN(cable)!=86) throw std::runtime_error("Native cable creation failed");
            gSDK->SetObjectClass(cable,classIndex);
            if (!gSDK->SetPluginObjectStyle(cable,gSDK->GetObjectInternalIndex(style)))
                throw std::runtime_error("Native style association failed after creation");
        }
        // Pass the actual handle directly; do not rely on the ambiguous VAR Python wrapper.
        gSDK->UpdatePIOFromStyle(cable);
        result["reset_returned"]=bool(gSDK->ResetObject(cable));
        if (!result["reset_returned"].get<bool>()) throw std::runtime_error("Native reset returned failure; inspect retained cable");
        result["status"]="ok";
        result["complete_insertion_verified"]=false;
        result["native_connections_verified"]=false;
    } catch (const std::exception& error) { result["error"]=error.what(); }
      catch (...) { result["error"]="Unknown native cable lifecycle failure"; }
    if (cable) { TXString uuid; if(gSDK->GetObjectUuid(cable,uuid)) result["object_id"]=BoundedText(uuid); }
    return result;
}

json GDTFExchange(const TXString& requestText) {
    namespace fs=std::filesystem;
    using namespace VectorWorks::Filing;
    using VWFC::VWObjects::VWParametricObj;
    json result={{"contract_version",1},{"status","error"},{"retry_safe",true}};
    try {
        std::string text(requestText.GetCharPtr());
        if(text.size()>16384) throw std::runtime_error("Request exceeds 16 KB");
        auto request=json::parse(text);
        if(!request.is_object()) throw std::runtime_error("JSON object required");
        auto operation=request.at("operation").get<std::string>();
        bool importing=operation=="import";
        if(!importing && operation!="export") throw std::runtime_error("Use import or export");
        std::set<std::string> keys={"operation","expected_document","object_id","path"};
        if(importing) keys.insert("mode");
        if(request.size()!=keys.size()) throw std::runtime_error("Incorrect request fields");
        for(auto it=request.begin();it!=request.end();++it)
            if(!keys.count(it.key()) || !it.value().is_string() || it.value().get<std::string>().find('\0')!=std::string::npos)
                throw std::runtime_error("Expected named string fields without NUL bytes");
        auto expected=fs::u8path(request.at("expected_document").get<std::string>());
        auto path=fs::u8path(request.at("path").get<std::string>());
        if(!expected.is_absolute() || !path.is_absolute() || _wcsicmp(path.extension().c_str(),L".gdtf")!=0)
            throw std::runtime_error("Absolute document and .gdtf file paths required");
        if(importing) {
            if(!fs::is_regular_file(path) || fs::file_size(path)>100*1024*1024)
                throw std::runtime_error("Import requires existing GDTF file up to 100 MB");
        } else if(fs::exists(path) || !fs::is_directory(path.parent_path()))
            throw std::runtime_error("Export requires unused destination in an existing directory");
        IFileIdentifierPtr active;bool saved=false;TXString activePath;
        if(!gSDK->GetActiveDocument(&active,saved) || !active || !saved || active->GetFileFullPath(activePath)!=kVCOMError_NoError)
            throw std::runtime_error("Saved active document required");
        if(_wcsicmp(fs::weakly_canonical(fs::u8path(activePath.GetCharPtr())).c_str(),fs::weakly_canonical(expected).c_str())!=0)
            throw std::runtime_error("Active document guard mismatch");
        auto uuid=request.at("object_id").get<std::string>();
        if(uuid.empty() || uuid.size()>128) throw std::runtime_error("Invalid Lighting Device UUID");
        auto h=gSDK->GetObjectByUuid(TXString(uuid.c_str()));
        if(!h || gSDK->GetObjectTypeN(h)!=86 || VWParametricObj(h).GetParametricName()!="Lighting Device")
            throw std::runtime_error("Expected native Lighting Device");
        auto parent=gSDK->ParentObject(h);
        if(!parent || gSDK->GetObjectTypeN(parent)!=31) throw std::runtime_error("Use a top-level design-layer Lighting Device");
        IImportExportGDTFPtr service(IID_ImportExportGDTF);
        IFileIdentifierPtr file(IID_FileIdentifier);
        if(!service || !file || file->Set(TXString(path.u8string().c_str()))!=kVCOMError_NoError)
            throw std::runtime_error("Native GDTF service/file unavailable");
        std::string mode;
        if(importing) {
            mode=request.at("mode").get<std::string>();
            if(mode.empty() || mode.size()>512) throw std::runtime_error("Explicit GDTF mode required");
        }
        result["object_id"]=uuid;result["operation"]=operation;result["path"]=path.u8string();
        result["retry_safe"]=false;
        auto code=importing ? service->ImportLightingDeviceGDTF(h,file,TXString(mode.c_str())) : service->ExportLightingDeviceGDTF(h,file);
        result["native_status_code"]=static_cast<Sint32>(code);
        if(code!=kVCOMError_NoError) throw std::runtime_error("Native GDTF operation returned failure; inspect retained fixture/destination");
        if(importing) {
            // Do not fabricate footprint, mode, Type ID or resource fields.
            result["requires_verification"]=true;
        } else {
            if(!fs::is_regular_file(path) || fs::file_size(path)==0) throw std::runtime_error("Native export produced no file");
            result["bytes"]=fs::file_size(path);
            result["scope"]="Native export may synthesize a generic GDTF; inspect content before treating it as manufacturer data.";
        }
        result["status"]="ok";
    } catch(const std::exception& error) { result["error"]=error.what(); }
      catch(...) { result["error"]="Unknown native GDTF failure"; }
    return result;
}

class NativeRoutines : public VWPluginLibraryRoutine {
public:
    void DispatchRoutine(Sint32 selector, VWPluginLibraryArgTable& args) override {
        if (selector == 4) {
            auto result=GDTFExchange(args.GetArgument(0).GetArgDynArrayChar());
            args.GetArgument(1).SetArgDynArrayCharVar(TXString(result.dump().c_str()));
            return;
        }
        if (selector == 3) {
            auto result=ProbeCableLifecycle(args.GetArgument(0).GetArgDynArrayChar());
            args.GetArgument(1).SetArgDynArrayCharVar(TXString(result.dump().c_str()));
            return;
        }
        if (selector == 2) {
            auto result=ExportSymbolLibrary(args.GetArgument(0).GetArgDynArrayChar());
            args.GetArgument(1).SetArgDynArrayCharVar(TXString(result.dump().c_str()));
            return;
        }
        if (selector == 1) {
            auto result = ReadElectricalComponents(args.GetArgument(0).GetArgHandle());
            args.GetArgument(1).SetArgDynArrayCharVar(TXString(result.dump().c_str()));
            return;
        }
        if (selector != 0) return;
        json result = {{"contract_version", 1}, {"status", "error"}};
        try {
            auto viewport = args.GetArgument(0).GetArgHandle();
            if (!viewport || gSDK->GetObjectTypeN(viewport) != 122)
                throw std::runtime_error("A native viewport handle is required");
            TXString uuid;
            if (!gSDK->GetObjectUuid(viewport, uuid)) throw std::runtime_error("Viewport UUID unavailable");
            result["viewport_id"] = uuid.GetCharPtr();
            InternalIndex styleIndex = 0;
            bool styleOK = gSDK->GetViewportStyle(viewport, styleIndex);
            TXString styleName;
            if (styleOK && styleIndex > 0) gSDK->GetObjectName(gSDK->InternalIndexToHandle(styleIndex), styleName);
            result["style"] = {{"native_ok", styleOK}, {"resource_index", styleIndex}, {"name", styleName.GetCharPtr()}};

            IAttrByDataOverridePtr vis(IID_AttrByDataOverride);
            result["data_visualization"] = {{"available", bool(vis)}};
            if (vis) {
                DataVisScope scope(vis, viewport);
                auto id = vis->GetViewportSchemeID(viewport);
                auto& d = result["data_visualization"];
                d["enabled"] = vis->GetOverrideEnabled();
                d["paused"] = vis->IsPaused();
                d["scheme_id"] = id.IsEmpty() ? "" : id.ToString().GetCharPtr();
                d["include_groups"] = vis->GetIncludeGroup();
                d["include_symbols"] = vis->GetIncludeSymbols();
                if (!id.IsEmpty()) {
                    TXString name;
                    std::vector<TColorEntry> colors;
                    std::vector<TVisibilityEntry> hidden;
                    vis->GetDataVisInfo(id, ESelectionParams::espApplied, name, colors, hidden);
                    d["scheme_name"] = name.GetCharPtr();
                    d["applied_color_entries"] = colors.size();
                    d["applied_hide_entries"] = hidden.size();
                }
            }
            result["status"] = "ok";
        }
        catch (const std::exception& error) { result["error"] = error.what(); }
        catch (...) { result["error"] = "Unknown native viewport inspection failure"; }
        args.GetArgument(1).SetArgDynArrayCharVar(TXString(result.dump().c_str()));
    }
};
}

namespace VwxBridge {
CExtVMNativeFunctions::CExtVMNativeFunctions(CallBackPtr cbp) : VWExtensionVSFunctions(cbp, functions) {}

BEGIN_VWVSFunctions(CExtVMNativeFunctions, "VMNativeFunctions", 1,
    0x1ce687a2, 0x191f, 0x47a8, 0xaa, 0x90, 0x73, 0xb5, 0x48, 0x1b, 0x3c, 0x21)
    eventSink->AddRoutine(SDK_NEW NativeRoutines(), true);
END_VWVSFunctions
}
