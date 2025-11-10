interface PipelineViewProps {
    deals: any[];
    onDealClick: (deal: any) => void;
    onNewDeal?: () => void;
}

export function PipelineView({ deals, onDealClick, onNewDeal }: PipelineViewProps) {
    const stages = ['Lead', 'Qualified', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost'];

    return (
        <div className="p-6">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Pipeline View</h2>
                {onNewDeal && (
                    <button
                        onClick={onNewDeal}
                        className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                    >
                        New Job
                    </button>
                )}
            </div>
            <div className="flex space-x-6 overflow-x-auto pb-4">
                {stages.map((stage) => (
                    <div key={stage} className="flex-shrink-0 w-80">
                        <div className="bg-gray-100 rounded-lg p-4">
                            <h3 className="font-semibold text-gray-900 mb-4">{stage}</h3>
                            <div className="space-y-3">
                                {deals
                                    .filter((deal) => deal.stage === stage)
                                    .map((deal) => (
                                        <div
                                            key={deal.id}
                                            onClick={() => onDealClick(deal)}
                                            className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 cursor-pointer hover:shadow-md transition-shadow"
                                        >
                                            <h4 className="font-medium text-gray-900">{deal.title}</h4>
                                            <p className="text-sm text-gray-600 mt-1">{deal.customer}</p>
                                            <div className="flex justify-between items-center mt-3">
                                                <span className="text-sm font-medium text-green-600">${deal.value}</span>
                                                <span className="text-xs text-gray-500">{deal.days} days</span>
                                            </div>
                                        </div>
                                    ))}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
