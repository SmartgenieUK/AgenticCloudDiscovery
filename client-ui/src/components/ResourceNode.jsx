import { Handle, Position } from "@xyflow/react";
import { memo } from "react";

const PROVIDER_COLORS = {
  "Microsoft.Compute": "#0078d4",
  "Microsoft.Network": "#00a4ef",
  "Microsoft.Storage": "#47b881",
  "Microsoft.Sql": "#e8590c",
  "Microsoft.DBforMySQL": "#e8590c",
  "Microsoft.DBforPostgreSQL": "#e8590c",
  "Microsoft.Web": "#9333ea",
  "Microsoft.KeyVault": "#d97706",
  "Microsoft.Authorization": "#64748b",
};

function getColor(providerNamespace) {
  return PROVIDER_COLORS[providerNamespace] || "#475569";
}

function getShortType(type) {
  if (!type) return "";
  const parts = type.split("/");
  return parts[parts.length - 1] || type;
}

function getIcon(type) {
  const short = getShortType(type).toLowerCase();
  if (short.includes("virtualmachine")) return "VM";
  if (short.includes("storageaccount")) return "ST";
  if (short.includes("virtualnetwork")) return "VN";
  if (short.includes("networksecuritygroup")) return "SG";
  if (short.includes("networkinterface")) return "NI";
  if (short.includes("publicipaddress")) return "IP";
  if (short.includes("loadbalancer")) return "LB";
  if (short.includes("privateendpoint")) return "PE";
  if (short.includes("routetable")) return "RT";
  if (short.includes("server")) return "DB";
  if (short.includes("site")) return "WA";
  if (short.includes("vault")) return "KV";
  if (short.includes("disk")) return "DK";
  if (short.includes("roleassignment")) return "RA";
  if (short.includes("policyassignment")) return "PA";
  return (type || "?")[0].toUpperCase();
}

const ResourceNode = memo(({ data, selected }) => {
  const color = getColor(data.provider_namespace);
  return (
    <div className={`rf-resource-node${selected ? " rf-resource-selected" : ""}`}>
      <Handle type="target" position={Position.Top} className="rf-handle" />
      <div className="rf-resource-header" style={{ background: color }}>
        <span className="rf-resource-icon">{getIcon(data.type)}</span>
        <span className="rf-resource-name" title={data.name}>{data.name}</span>
      </div>
      <div className="rf-resource-body">
        <span className="rf-resource-type" title={data.type}>{getShortType(data.type)}</span>
        {data.location && <span className="rf-resource-location">{data.location}</span>}
      </div>
      <Handle type="source" position={Position.Bottom} className="rf-handle" />
    </div>
  );
});

ResourceNode.displayName = "ResourceNode";
export default ResourceNode;
