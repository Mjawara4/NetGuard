import React, { useCallback, useState } from 'react';
import ReactFlow, {
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Server, Router, Wifi, Cloud } from 'lucide-react';
import api from '../api';
import { PageHeader } from '../components/ui';

const initialNodes = [];
const initialEdges = [];

export default function NetworkMap() {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
    const [loading, setLoading] = useState(true);

    React.useEffect(() => {
        fetchTopology();
    }, []);

    const fetchTopology = async () => {
        try {
            const sitesRes = await api.get('/inventory/sites');
            const devicesRes = await api.get('/inventory/devices');

            const newNodes = [];
            const newEdges = [];

            // 1. Internet Cloud Node
            // This node's fill is `transparent`, so its label sits on the page
            // ground and does need a dark variant -- unlike the device nodes below.
            newNodes.push({
                id: 'internet',
                data: {
                    label: (
                        <div className="flex flex-col items-center text-ink-900 dark:text-ink-100">
                            <Cloud size={32} className="text-signal-600 dark:text-signal-300" /> Internet
                        </div>
                    )
                },
                position: { x: 400, y: 0 },
                style: { width: 100, height: 80, border: 'none', background: 'transparent' }
            });

            // 2. Sites
            sitesRes.data.forEach((site, idx) => {
                const siteNodeId = `site-${site.id}`;
                newNodes.push({
                    id: siteNodeId,
                    data: { label: <div className="font-bold p-2 border border-ink-300 dark:border-ink-600 rounded-sm bg-white dark:bg-ink-700 shadow text-ink-900 dark:text-ink-50">{site.name}</div> },
                    position: { x: 200 + (idx * 300), y: 150 },
                    type: 'group',
                    // ink-100 at 50%. React Flow group fills take a literal colour.
                    style: { width: 300, height: 400, backgroundColor: 'rgba(236, 239, 238, 0.5)' }
                });

                // Connect Internet to Site (Conceptual)
                newEdges.push({ id: `e-internet-${siteNodeId}`, source: 'internet', target: siteNodeId, animated: true });

                // 3. Devices in Site
                const siteDevices = devicesRes.data.filter(d => d.site_id === site.id);
                siteDevices.forEach((dev, devIdx) => {
                    const devNodeId = `dev-${dev.id}`;
                    let Icon = Server;
                    if (dev.device_type === 'router') Icon = Router;
                    if (dev.device_type === 'switch') Icon = Server;

                    const isOnline = dev.is_active;

                    // BUG FIX, not a restyle. A default React Flow node is filled
                    // `background-color: white` by reactflow's own stylesheet, which has
                    // no dark variant -- the node stays white in dark mode. The old
                    // `dark:text-white` therefore painted white text on a white box:
                    // measured 1.00:1, i.e. every device label on this map was
                    // literally invisible at night. Colours inside these nodes are
                    // deliberately light-mode-only, because the ground they sit on is
                    // white in BOTH themes; adding a dark: variant here is what
                    // created the bug.
                    newNodes.push({
                        id: devNodeId,
                        data: {
                            label: (
                                <div className="flex flex-col items-center">
                                    <div className={`p-2 rounded-full ${isOnline ? 'bg-up/10 text-up' : 'bg-down/10 text-down'}`}>
                                        <Icon size={24} />
                                    </div>
                                    <div className="text-xs font-bold mt-1 max-w-[100px] truncate text-ink-900">{dev.name}</div>
                                    <div className="text-xs text-ink-500">{dev.ip_address}</div>
                                </div>
                            )
                        },
                        position: { x: 250 + (idx * 300), y: 250 + (devIdx * 100) },
                        parentNode: undefined
                    });

                    if (dev.device_type === 'router') {
                        // `up`, as a literal -- React Flow edge strokes take no classes.
                        newEdges.push({ id: `e-internet-${devNodeId}`, source: 'internet', target: devNodeId, animated: true, style: { stroke: '#2F7D62', strokeWidth: 2 } });
                    } else {
                        const siteRouter = siteDevices.find(d => d.device_type === 'router');
                        if (siteRouter) {
                            newEdges.push({ id: `e-${siteRouter.id}-${dev.id}`, source: `dev-${siteRouter.id}`, target: devNodeId });
                        }
                    }
                });
            });

            setNodes(newNodes);
            setEdges(newEdges);
            setLoading(false);

        } catch (e) {
            console.error("Topo failed", e);
            setLoading(false);
        }
    };

    return (
        <div className="h-screen w-full bg-ink-50 dark:bg-ink-900 flex flex-col">
            <div className="bg-white dark:bg-ink-800 shadow p-4 z-10">
                <PageHeader title="Network" accent="Topology" subtitle="Visualize your infrastructure and device relationships." />
            </div>
            {loading && (
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                        <div className="w-12 h-12 border-4 border-signal-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                        <p className="font-medium text-ink-500 dark:text-ink-400 text-xs animate-pulse">Mapping topology...</p>
                    </div>
                </div>
            )}
            <div className={`flex-1 ${loading ? 'hidden' : ''}`}>
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    fitView
                >
                    <Controls />
                    <MiniMap />
                    <Background gap={12} size={1} />
                </ReactFlow>
            </div>
        </div>
    );
}
