import { useState, useEffect } from 'react';

interface RecordViewProps {
    record: any;
    onUpdate?: (recordId: string, updates: any) => void;
    files?: any[]; // Files attached to this record
}

export function RecordView({ record, onUpdate, files }: RecordViewProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [editTitle, setEditTitle] = useState('');
    const [editStatus, setEditStatus] = useState('');
    const [editOwner, setEditOwner] = useState('');
    const [editNextAction, setEditNextAction] = useState('');

    useEffect(() => {
        if (record) {
            setEditTitle(record.title || '');
            setEditStatus(record.status || '');
            setEditOwner(record.owner || '');
            setEditNextAction(record.next_action || '');
        }
    }, [record]);

    const handleSave = async () => {
        if (!onUpdate || !record) return;

        const updates: any = {};
        if (editTitle !== record.title) updates.title = editTitle;
        if (editStatus !== record.status) updates.status = editStatus;
        if (editOwner !== record.owner) updates.owner = editOwner;
        if (editNextAction !== record.next_action) updates.next_action = editNextAction;

        if (Object.keys(updates).length > 0) {
            await onUpdate(record.id, updates);
            setIsEditing(false);
        }
    };

    const handleCancel = () => {
        setEditTitle(record?.title || '');
        setEditStatus(record?.status || '');
        setEditOwner(record?.owner || '');
        setEditNextAction(record?.next_action || '');
        setIsEditing(false);
    };

    if (!record) return <div className="p-6">Select a record to view details</div>;

    return (
        <div className="flex h-full">
            {/* Left Column - Details */}
            <div className="flex-1 p-6 border-r border-gray-200">
                <div className="mb-6">
                    <div className="flex justify-between items-start">
                        {isEditing ? (
                            <input
                                type="text"
                                value={editTitle}
                                onChange={(e) => setEditTitle(e.target.value)}
                                className="text-2xl font-bold text-gray-900 border border-gray-300 rounded px-2 py-1 w-full"
                                placeholder="Job title"
                            />
                        ) : (
                            <h2 className="text-2xl font-bold text-gray-900">{record.title}</h2>
                        )}
                        <div className="flex gap-2">
                            {isEditing ? (
                                <>
                                    <button
                                        onClick={handleSave}
                                        className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700"
                                    >
                                        Save
                                    </button>
                                    <button
                                        onClick={handleCancel}
                                        className="bg-gray-300 text-gray-700 px-3 py-1 rounded text-sm hover:bg-gray-400"
                                    >
                                        Cancel
                                    </button>
                                </>
                            ) : (
                                onUpdate && (
                                    <button
                                        onClick={() => setIsEditing(true)}
                                        className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700"
                                    >
                                        Edit
                                    </button>
                                )
                            )}
                        </div>
                    </div>
                    <p className="text-gray-600 mt-1">{record.customer}</p>
                </div>

                <div className="grid grid-cols-2 gap-6 mb-6">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Value</label>
                        <div className="text-lg font-semibold text-green-600">${record.value || 0}</div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                        {isEditing ? (
                            <select
                                value={editStatus}
                                onChange={(e) => setEditStatus(e.target.value)}
                                className="w-full px-2 py-1 border border-gray-300 rounded"
                                aria-label="Job status"
                            >
                                <option value="Lead">Lead</option>
                                <option value="Qualified">Qualified</option>
                                <option value="Proposal">Proposal</option>
                                <option value="Active">Active</option>
                                <option value="Closed Won">Closed Won</option>
                                <option value="Closed Lost">Closed Lost</option>
                            </select>
                        ) : (
                            <div className="text-lg font-semibold">{record.status}</div>
                        )}
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Owner</label>
                        {isEditing ? (
                            <input
                                type="text"
                                value={editOwner}
                                onChange={(e) => setEditOwner(e.target.value)}
                                className="w-full px-2 py-1 border border-gray-300 rounded"
                                placeholder="Owner name"
                            />
                        ) : (
                            <div>{record.owner || 'Unassigned'}</div>
                        )}
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Next Action</label>
                        {isEditing ? (
                            <input
                                type="text"
                                value={editNextAction}
                                onChange={(e) => setEditNextAction(e.target.value)}
                                className="w-full px-2 py-1 border border-gray-300 rounded"
                                placeholder="Next action"
                            />
                        ) : (
                            <div>{record.next_action || 'No action planned'}</div>
                        )}
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Created</label>
                        <div>{record.created_at ? new Date(record.created_at).toLocaleDateString() : 'Unknown'}</div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Last Updated</label>
                        <div>{record.updated_at ? new Date(record.updated_at).toLocaleDateString() : 'Unknown'}</div>
                    </div>
                </div>

                <div className="mb-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">Description</h3>
                    <p className="text-gray-700">{record.description}</p>
                </div>

                <div className="mb-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">Activity</h3>
                    <div className="space-y-3">
                        {record.activities?.map((activity: any, i: number) => (
                            <div key={i} className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
                                <div className="w-2 h-2 bg-blue-500 rounded-full mt-2"></div>
                                <div className="flex-1">
                                    <p className="text-sm text-gray-900">{activity.description}</p>
                                    <p className="text-xs text-gray-500 mt-1">{new Date(activity.timestamp).toLocaleString()}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Right Column - Messages & Docs */}
            <div className="w-96 p-6">
                <div className="mb-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">Messages</h3>
                    <div className="space-y-3 max-h-64 overflow-y-auto">
                        {record.messages?.map((message: any, i: number) => (
                            <div key={i} className="p-3 bg-blue-50 rounded-lg">
                                <p className="text-sm text-gray-900">{message.content}</p>
                                <p className="text-xs text-gray-500 mt-1">{message.from} • {new Date(message.timestamp).toLocaleString()}</p>
                            </div>
                        ))}
                    </div>
                </div>

                <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">Documents</h3>
                    <div className="space-y-2">
                        {record.documents?.map((doc: any, i: number) => (
                            <div key={i} className="flex items-center justify-between p-2 border border-gray-200 rounded">
                                <span className="text-sm text-gray-900">{doc.name}</span>
                                <button className="text-blue-600 hover:text-blue-800 text-sm">Download</button>
                            </div>
                        ))}
                    </div>
                </div>

                {/* AccuLynx Files */}
                {files && files.length > 0 && (
                    <div className="mt-6">
                        <h3 className="text-lg font-semibold text-gray-900 mb-3">Attached Files (AccuLynx)</h3>
                        <div className="space-y-2">
                            {files.map((file: any, i: number) => (
                                <div key={i} className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded">
                                    <div className="flex items-center space-x-2">
                                        <span className="text-sm text-gray-900">{file.name}</span>
                                        <span className="text-xs text-blue-600 bg-blue-100 px-2 py-1 rounded">AccuLynx</span>
                                    </div>
                                    {file.url ? (
                                        <a
                                            href={file.url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                                        >
                                            Open
                                        </a>
                                    ) : (
                                        <span className="text-xs text-gray-400">no url</span>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
