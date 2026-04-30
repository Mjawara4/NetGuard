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
            newNodes.push({
                id: 'internet',
                data: { label: <div className="flex flex-col items-center"><Cloud size={32} color="#3b82f6" /> Internet</div> },
                position: { x: 400, y: 0 },
                style: { width: 100, height: 80, border: 'none', background: 'transparent' }
            });

            // 2. Sites
            sitesRes.data.forEach((site, idx) => {
                const siteNodeId = `site-${site.id}`;
                newNodes.push({
                    id: siteNodeId,
                    data: { label: <div className="font-bold p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 shadow dark:text-white">{site.name}</div> },
                    position: { x: 200 + (idx * 300), y: 150 },
                    type: 'group',
                    style: { width: 300, height: 400, backgroundColor: 'rgba(240, 240, 240, 0.5)' }
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

                    newNodes.push({
                        id: devNodeId,
                        data: {
                            label: (
                                <div className="flex flex-col items-center">
                                    <div className={`p-2 rounded-full ${isOnline ? 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400'}`}>
                                        <Icon size={24} />
                                    </div>
                                    <div className="text-xs font-bold mt-1 max-w-[100px] truncate dark:text-white">{dev.name}</div>
                                    <div className="text-[10px] text-gray-500 dark:text-gray-400">{dev.ip_address}</div>
                                </div>
                            )
                        },
                        position: { x: 250 + (idx * 300), y: 250 + (devIdx * 100) },
                        parentNode: undefined
                    });

                    if (dev.device_type === 'router') {
                        newEdges.push({ id: `e-internet-${devNodeId}`, source: 'internet', target: devNodeId, animated: true, style: { stroke: '#22c55e', strokeWidth: 2 } });
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
        <div className="h-screen w-full bg-gray-50 dark:bg-gray-900 flex flex-col">
            <div className="bg-white dark:bg-gray-800 shadow p-4 z-10">
                <PageHeader title="Network" accent="Topology" subtitle="Visualize your infrastructure and device relationships." />
            </div>
            {loading && (
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                        <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                        <p className="font-black text-gray-400 dark:text-gray-500 uppercase tracking-widest text-xs animate-pulse">Mapping topology...</p>
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
