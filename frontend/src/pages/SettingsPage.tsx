import { useState } from 'react'
import {
  LayoutDashboard,
  Server,
  Bell,
  TestTube2,
  Palette,
  Save,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { cn } from '@/lib/utils'

type Settings = {
  companyName: string
  timezone: string
  dateFormat: string
  slackWebhook: string
  pagerdutyKey: string
  githubToken: string
  emailAlerts: boolean
  slackAlerts: boolean
  anomalyThreshold: string
  sqlAgentEnabled: boolean
  feedbackAgentEnabled: boolean
  experimentAgentEnabled: boolean
  rootCauseAgentEnabled: boolean
  decisionAgentEnabled: boolean
  maxIterations: number
  theme: string
  compactMode: boolean
  [key: string]: string | number | boolean
}

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'general' | 'integrations' | 'notifications' | 'agents' | 'appearance'>('general')
  const [settings, setSettings] = useState<Settings>({
    // General
    companyName: 'Product Intelligence Inc',
    timezone: 'America/New_York',
    dateFormat: 'MM/DD/YYYY',
    // Integrations
    slackWebhook: '',
    pagerdutyKey: '',
    githubToken: '',
    // Notifications
    emailAlerts: true,
    slackAlerts: false,
    anomalyThreshold: 'medium',
    // Agents
    sqlAgentEnabled: true,
    feedbackAgentEnabled: true,
    experimentAgentEnabled: true,
    rootCauseAgentEnabled: true,
    decisionAgentEnabled: true,
    maxIterations: 10,
    // Appearance
    theme: 'system',
    compactMode: false,
  })

  const iconMap = {
  palette: Palette,
  server: Server,
  bell: Bell,
  'test-tube': TestTube2,
}

type TabId = 'general' | 'integrations' | 'notifications' | 'agents' | 'appearance';

const tabs: { id: TabId; label: string; icon: keyof typeof iconMap }[] = [
    { id: 'general', label: 'General', icon: 'palette' },
    { id: 'integrations', label: 'Integrations', icon: 'server' },
    { id: 'notifications', label: 'Notifications', icon: 'bell' },
    { id: 'agents', label: 'Agents', icon: 'test-tube' },
    { id: 'appearance', label: 'Appearance', icon: 'palette' },
  ]

  const handleChange = (key: keyof Settings, value: string | number | boolean) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  const handleSave = () => {
    // In real app, save to API
    console.log('Saving settings:', settings)
    alert('Settings saved!')
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 mt-1">Configure your Product Intelligence workspace</p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-48 flex-shrink-0">
          <nav className="space-y-1" aria-label="Settings categories">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'w-full text-left px-4 py-3 rounded-lg text-sm font-medium transition-colors',
                  activeTab === tab.id
                    ? 'bg-primary-50 text-primary-700 border-r-2 border-primary-600'
                    : 'text-gray-600 hover:bg-gray-50'
                )}
              >
                {(() => {
                  const Icon = iconMap[tab.icon];
                  return Icon ? <Icon className="w-4 h-4 inline mr-2" /> : null;
                })()}
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            {activeTab === 'general' && (
              <div className="space-y-6 max-w-2xl">
                <h2 className="text-lg font-semibold text-gray-900">General Settings</h2>
                <div className="space-y-4">
                  <div>
                    <label className="label block mb-1">Company Name</label>
                    <input
                      type="text"
                      value={settings.companyName}
                      onChange={(e) => handleChange('companyName', e.target.value)}
                      className="input"
                    />
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="label block mb-1">Timezone</label>
                      <select value={settings.timezone} onChange={(e) => handleChange('timezone', e.target.value)} className="input">
                        <option value="America/New_York">Eastern Time (ET)</option>
                        <option value="America/Chicago">Central Time (CT)</option>
                        <option value="America/Denver">Mountain Time (MT)</option>
                        <option value="America/Los_Angeles">Pacific Time (PT)</option>
                        <option value="UTC">UTC</option>
                      </select>
                    </div>
                    <div>
                      <label className="label block mb-1">Date Format</label>
                      <select value={settings.dateFormat} onChange={(e) => handleChange('dateFormat', e.target.value)} className="input">
                        <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                        <option value="DD/MM/YYYY">DD/MM/YYYY</option>
                        <option value="YYYY-MM-DD">YYYY-MM-DD</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'integrations' && (
              <div className="space-y-6 max-w-2xl">
                <h2 className="text-lg font-semibold text-gray-900">Third-Party Integrations</h2>
                <div className="space-y-4">
                  <div className="card p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-medium text-gray-900">Slack</h3>
                        <p className="text-sm text-gray-500">Receive alerts and notifications in Slack channels</p>
                      </div>
                      <input
                        type="text"
                        placeholder="Slack Webhook URL"
                        value={settings.slackWebhook}
                        onChange={(e) => handleChange('slackWebhook', e.target.value)}
                        className="input w-80"
                      />
                    </div>
                  </div>
                  <div className="card p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-medium text-gray-900">PagerDuty</h3>
                        <p className="text-sm text-gray-500">Escalate critical anomalies to on-call rotations</p>
                      </div>
                      <input
                        type="password"
                        placeholder="PagerDuty API Key"
                        value={settings.pagerdutyKey}
                        onChange={(e) => handleChange('pagerdutyKey', e.target.value)}
                        className="input w-80"
                      />
                    </div>
                  </div>
                  <div className="card p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-medium text-gray-900">GitHub</h3>
                        <p className="text-sm text-gray-500">Link investigations to GitHub issues and PRs</p>
                      </div>
                      <input
                        type="password"
                        placeholder="GitHub Personal Access Token"
                        value={settings.githubToken}
                        onChange={(e) => handleChange('githubToken', e.target.value)}
                        className="input w-80"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'notifications' && (
              <div className="space-y-6 max-w-2xl">
                <h2 className="text-lg font-semibold text-gray-900">Notification Preferences</h2>
                <div className="space-y-4">
                  <div className="card p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-medium text-gray-900">Email Alerts</h3>
                        <p className="text-sm text-gray-500">Receive anomaly alerts via email</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={settings.emailAlerts}
                        onChange={(e) => handleChange('emailAlerts', e.target.checked)}
                        className="w-5 h-5 text-primary-600 border-gray-300 rounded"
                      />
                    </div>
                  </div>
                  <div className="card p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-medium text-gray-900">Slack Alerts</h3>
                        <p className="text-sm text-gray-500">Send anomaly alerts to Slack</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={settings.slackAlerts}
                        onChange={(e) => handleChange('slackAlerts', e.target.checked)}
                        className="w-5 h-5 text-primary-600 border-gray-300 rounded"
                      />
                    </div>
                  </div>
                  <div className="card p-6">
                    <div>
                      <label className="label block mb-1">Anomaly Alert Threshold</label>
                      <select value={settings.anomalyThreshold} onChange={(e) => handleChange('anomalyThreshold', e.target.value)} className="input">
                        <option value="low">Low (all anomalies)</option>
                        <option value="medium">Medium and above</option>
                        <option value="high">High and critical only</option>
                        <option value="critical">Critical only</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'agents' && (
              <div className="space-y-6 max-w-2xl">
                <h2 className="text-lg font-semibold text-gray-900">Agent Configuration</h2>
                <div className="space-y-4">
                  {[
                    { key: 'sqlAgentEnabled', label: 'SQL Investigation Agent', desc: 'Autonomous SQL query generation and analysis' },
                    { key: 'feedbackAgentEnabled', label: 'Feedback Intelligence Agent', desc: 'RAG-based customer feedback analysis' },
                    { key: 'experimentAgentEnabled', label: 'Experiment Analysis Agent', desc: 'A/B test statistical analysis' },
                    { key: 'rootCauseAgentEnabled', label: 'Root Cause Agent', desc: 'Multi-source evidence synthesis' },
                    { key: 'decisionAgentEnabled', label: 'Decision Agent', desc: 'RICE-based recommendation prioritization' },
                  ].map(({ key, label, desc }) => (
                    <div key={key} className="card p-6 flex items-center justify-between">
                      <div>
                        <h3 className="font-medium text-gray-900">{label}</h3>
                        <p className="text-sm text-gray-500">{desc}</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={settings[key] as boolean}
                        onChange={(e) => handleChange(key, e.target.checked)}
                        className="w-5 h-5 text-primary-600 border-gray-300 rounded"
                      />
                    </div>
                  ))}
                  <div className="card p-6">
                    <label className="label block mb-1">Max Investigation Iterations</label>
                    <input
                      type="number"
                      min={1}
                      max={50}
                      value={settings.maxIterations}
                      onChange={(e) => handleChange('maxIterations', parseInt(e.target.value))}
                      className="input w-24"
                    />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'appearance' && (
              <div className="space-y-6 max-w-2xl">
                <h2 className="text-lg font-semibold text-gray-900">Appearance</h2>
                <div className="space-y-4">
                  <div className="card p-6">
                    <label className="label block mb-1">Theme</label>
                    <select value={settings.theme} onChange={(e) => handleChange('theme', e.target.value)} className="input">
                      <option value="system">System</option>
                      <option value="light">Light</option>
                      <option value="dark">Dark</option>
                    </select>
                  </div>
                  <div className="card p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-medium text-gray-900">Compact Mode</h3>
                        <p className="text-sm text-gray-500">Reduce spacing for denser information display</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={settings.compactMode}
                        onChange={(e) => handleChange('compactMode', e.target.checked)}
                        className="w-5 h-5 text-primary-600 border-gray-300 rounded"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Save Button */}
            <div className="flex justify-end pt-6 border-t border-gray-200">
              <button onClick={handleSave} className="btn-primary">
                Save Settings
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}