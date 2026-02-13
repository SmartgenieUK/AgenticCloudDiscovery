import { memo, useCallback, useState } from "react";

const LABEL_ICONS = {
  tenant: "\u{1F3E2}",
  subscription: "\u{1F4E6}",
  resource_group: "\u{1F4C1}",
  resource: "\u{1F4E4}",
};

const TreeNode = memo(({ node, depth, selectedId, onSelect }) => {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children && node.children.length > 0;

  const toggle = useCallback((e) => {
    e.stopPropagation();
    setExpanded((v) => !v);
  }, []);

  const handleClick = useCallback(() => {
    onSelect(node);
  }, [node, onSelect]);

  const isSelected = selectedId === node.id;

  return (
    <div className="tree-node-wrapper">
      <div
        className={`tree-node${isSelected ? " tree-node-selected" : ""}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={handleClick}
        role="treeitem"
        aria-selected={isSelected}
      >
        {hasChildren ? (
          <button className="tree-node-toggle" onClick={toggle} aria-label={expanded ? "collapse" : "expand"}>
            {expanded ? "\u25BE" : "\u25B8"}
          </button>
        ) : (
          <span className="tree-node-toggle-spacer" />
        )}
        <span className="tree-node-label">
          {node.name || node.id}
        </span>
        {node.type && (
          <span className="tree-node-type">{node.type.split("/").pop()}</span>
        )}
        {hasChildren && (
          <span className="tree-node-count">{node.children.length}</span>
        )}
      </div>
      {expanded && hasChildren && (
        <div className="tree-node-children" role="group">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
});

TreeNode.displayName = "TreeNode";

const TopologyTree = ({ hierarchy, selectedId, onSelect }) => {
  if (!hierarchy) return <div className="tree-empty">No hierarchy data</div>;

  return (
    <div className="topology-tree" role="tree">
      <TreeNode
        node={hierarchy}
        depth={0}
        selectedId={selectedId}
        onSelect={onSelect}
      />
    </div>
  );
};

export default TopologyTree;
