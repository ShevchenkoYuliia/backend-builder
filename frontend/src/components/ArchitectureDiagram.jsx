import React, { useEffect } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const nodeWidth = 250;

const getLayoutedElements = (nodes, edges, direction = 'TB') => {
  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({ rankdir: direction });

  nodes.forEach((node) => {
    // Height estimation based on field count
    const fieldCount = node.data?.fields?.length || 1;
    dagreGraph.setNode(node.id, { width: nodeWidth, height: fieldCount * 28 + 50 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = isHorizontal ? Position.Left : Position.Top;
    node.sourcePosition = isHorizontal ? Position.Right : Position.Bottom;
    
    // Shift position from center to top-left for React Flow
    const fieldCount = node.data?.fields?.length || 1;
    node.position = {
      x: nodeWithPosition.x - nodeWidth / 2,
      y: nodeWithPosition.y - (fieldCount * 28 + 50) / 2,
    };
    return node;
  });

  return { nodes, edges };
};

const EntityNode = ({ data }) => {
  return (
    <div style={{ background: '#181a19ff', border: '1px solid #10b981', borderRadius: '8px', minWidth: '220px', fontSize: '12px', color: '#fff', overflow: 'hidden', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)' }}>
      <Handle type="target" position={Position.Top} style={{ background: '#10b981', width: '8px', height: '8px' }} />
      <div style={{ background: '#10b981', padding: '8px 12px', fontWeight: 'bold', color: '#000', display: 'flex', justifyContent: 'space-between' }}>
        <span>{data.name}</span>
      </div>
      <div style={{ padding: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {data.fields.map((field, idx) => (
          <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: idx === data.fields.length - 1 ? 'none' : '1px solid #2d312f' }}>
            <span>{field.name} {field.required ? '*' : ''}</span>
            <span style={{ color: '#14b8a6', fontFamily: 'monospace' }}>{field.type}</span>
          </div>
        ))}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#10b981', width: '8px', height: '8px' }} />
    </div>
  );
};

const nodeTypes = {
  entity: EntityNode,
};

export default function ArchitectureDiagram({ project }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (!project || !project.entities) return;

    const initialNodes = project.entities.map((entity) => ({
      id: entity.name,
      type: 'entity',
      data: { name: entity.name, fields: entity.fields || [] },
      position: { x: 0, y: 0 }
    }));

    const initialEdges = [];
    project.entities.forEach((entity) => {
      (entity.relations || []).forEach((rel) => {
        const targetEntity = project.entities.find(e => e.name === rel.target_entity);
        if (targetEntity) {
          initialEdges.push({
            id: `e-${entity.name}-${rel.target_entity}-${rel.name}`,
            source: entity.name,
            target: rel.target_entity,
            label: `${rel.name} (${rel.relation_type.replace(/_/g, ' ')})`,
            labelStyle: { fill: '#a3a3a3', fontWeight: 600, fontSize: 10 },
            labelBgStyle: { fill: '#181a19ff', fillOpacity: 0.8 },
            style: { stroke: '#4f46e5', strokeWidth: 2 },
            animated: true,
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: '#4f46e5',
            },
          });
        }
      });
    });

    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      initialNodes,
      initialEdges,
      'TB' // Top to Bottom layout
    );

    setNodes([...layoutedNodes]);
    setEdges([...layoutedEdges]);
  }, [project, setNodes, setEdges]);

  return (
    <div style={{ width: '100%', height: '700px', background: '#0a0a0a', borderRadius: '8px', overflow: 'hidden', border: '1px solid #2d312f' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-right"
      >
        <Background color="#2d312f" gap={16} />
        <Controls style={{ fill: '#fff' }} />
        <MiniMap nodeColor="#10b981" maskColor="rgba(0,0,0,0.5)" style={{ background: '#1c1f1e' }} />
      </ReactFlow>
    </div>
  );
}
