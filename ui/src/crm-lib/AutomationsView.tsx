import { useState } from 'react';

interface AutomationRule {
    id: string;
    name: string;
    trigger: {
        event: string;
        conditions: any[];
    };
    actions: any[];
    enabled: boolean;
}

interface AutomationsViewProps {
    rules: AutomationRule[];
    onRuleUpdate: (rule: AutomationRule) => void;
    onRuleDelete: (id: string) => void;
}

export function AutomationsView({ rules, onRuleUpdate, onRuleDelete }: AutomationsViewProps) {
    const [editingRule, setEditingRule] = useState<AutomationRule | null>(null);

    return (
        <div className="p-6">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Automations</h2>
                <button className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
                    + New Rule
                </button>
            </div>

            <div className="space-y-4">
                {rules.map((rule) => (
                    <div key={rule.id} className="bg-white border border-gray-200 rounded-lg p-6">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center space-x-3">
                                <h3 className="text-lg font-semibold text-gray-900">{rule.name}</h3>
                                <label className="flex items-center">
                                    <input
                                        type="checkbox"
                                        checked={rule.enabled}
                                        onChange={(e) => onRuleUpdate({ ...rule, enabled: e.target.checked })}
                                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                    />
                                    <span className="ml-2 text-sm text-gray-600">Enabled</span>
                                </label>
                            </div>
                            <div className="flex space-x-2">
                                <button
                                    onClick={() => setEditingRule(rule)}
                                    className="text-blue-600 hover:text-blue-800 text-sm"
                                >
                                    Edit
                                </button>
                                <button
                                    onClick={() => onRuleDelete(rule.id)}
                                    className="text-red-600 hover:text-red-800 text-sm"
                                >
                                    Delete
                                </button>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <h4 className="font-medium text-gray-900 mb-2">When</h4>
                                <div className="p-3 bg-gray-50 rounded">
                                    <div className="text-sm text-gray-700">
                                        <strong>{rule.trigger.event}</strong>
                                    </div>
                                    {rule.trigger.conditions.map((condition, i) => (
                                        <div key={i} className="text-xs text-gray-600 mt-1">
                                            {condition.field} {condition.operator} {condition.value}
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <h4 className="font-medium text-gray-900 mb-2">Then</h4>
                                <div className="space-y-2">
                                    {rule.actions.map((action, i) => (
                                        <div key={i} className="p-2 bg-blue-50 rounded text-sm">
                                            <strong>{action.type}:</strong> {action.description}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {editingRule && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg p-6 w-full max-w-2xl">
                        <h3 className="text-lg font-semibold mb-4">Edit Automation Rule</h3>
                        {/* Rule editing form would go here */}
                        <div className="flex justify-end space-x-3 mt-6">
                            <button
                                onClick={() => setEditingRule(null)}
                                className="px-4 py-2 text-gray-600 hover:text-gray-800"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => {
                                    if (editingRule) onRuleUpdate(editingRule);
                                    setEditingRule(null);
                                }}
                                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                            >
                                Save
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
