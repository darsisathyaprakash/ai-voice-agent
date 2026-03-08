import { useState, useEffect, useCallback } from 'react'
import { 
  getHealth, 
  getHealthReady,
  getPatients, 
  getDoctors, 
  getAppointments, 
  getCampaigns,
  createPatient,
  createAppointment,
  createCampaign,
  type Patient,
  type Doctor,
  type Appointment,
  type Campaign
} from './api'

type Tab = 'dashboard' | 'patients' | 'doctors' | 'appointments' | 'campaigns'

// Modal types
type ModalType = 'none' | 'patient' | 'appointment' | 'campaign'

interface HealthInfo {
  status: string;
  database: boolean;
  redis: boolean;
}

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard')
  const [healthInfo, setHealthInfo] = useState<HealthInfo | null>(null)
  const [patients, setPatients] = useState<Patient[]>([])
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [activeModal, setActiveModal] = useState<ModalType>('none')

  useEffect(() => {
    loadHealth()
  }, [])

  useEffect(() => {
    loadTabData()
  }, [activeTab])

  // Clear messages after 3 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [successMessage])

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [error])

  const loadHealth = async () => {
    try {
      // Try to get detailed health status
      const [basic, ready] = await Promise.all([
        getHealth().catch(() => null),
        getHealthReady().catch(() => null),
      ])
      
      setHealthInfo({
        status: basic?.status || (ready?.status === 'ready' ? 'healthy' : 'unhealthy'),
        database: ready?.checks?.database ?? false,
        redis: ready?.checks?.redis ?? false,
      })
    } catch {
      setHealthInfo(null)
    }
  }

  const loadTabData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      switch (activeTab) {
        case 'patients':
          setPatients(await getPatients())
          break
        case 'doctors':
          setDoctors(await getDoctors())
          break
        case 'appointments':
          setAppointments(await getAppointments())
          // Also load doctors and patients for the appointment form
          setDoctors(await getDoctors())
          setPatients(await getPatients())
          break
        case 'campaigns':
          setCampaigns(await getCampaigns())
          break
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [activeTab])

  const refreshData = async () => {
    await loadTabData()
    setSuccessMessage('Data refreshed successfully')
  }

  const openModal = (type: ModalType) => {
    setActiveModal(type)
  }

  const closeModal = () => {
    setActiveModal('none')
  }

  // Handler for creating a patient
  const handleCreatePatient = async (data: {
    first_name: string
    last_name: string
    phone: string
    email?: string
    preferred_language: string
  }) => {
    try {
      await createPatient(data)
      closeModal()
      setSuccessMessage('Patient created successfully!')
      if (activeTab === 'patients') {
        await loadTabData()
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create patient')
    }
  }

  // Handler for creating an appointment
  const handleCreateAppointment = async (data: {
    patient_id: string
    doctor_id: string
    appointment_date: string
    start_time: string
    reason?: string
  }) => {
    try {
      await createAppointment({
        patient_id: data.patient_id,
        doctor_id: data.doctor_id,
        scheduled_date: data.appointment_date,
        scheduled_time: data.start_time,
        notes: data.reason,
      })
      closeModal()
      setSuccessMessage('Appointment booked successfully!')
      if (activeTab === 'appointments') {
        await loadTabData()
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create appointment')
    }
  }

  // Handler for creating a campaign
  const handleCreateCampaign = async (data: {
    name: string
    campaign_type: string
    message_template: Record<string, string>
  }) => {
    try {
      await createCampaign(data)
      closeModal()
      setSuccessMessage('Campaign created successfully!')
      if (activeTab === 'campaigns') {
        await loadTabData()
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create campaign')
    }
  }

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'patients', label: 'Patients', icon: '👥' },
    { id: 'doctors', label: 'Doctors', icon: '👨‍⚕️' },
    { id: 'appointments', label: 'Appointments', icon: '📅' },
    { id: 'campaigns', label: 'Campaigns', icon: '📢' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">🎙️</span>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Voice AI Agent</h1>
              <p className="text-sm text-gray-500">Clinical Appointment System</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={refreshData} className="btn btn-secondary text-sm">
              🔄 Refresh
            </button>
            <span className={`badge ${healthInfo?.status === 'healthy' ? 'badge-success' : 'badge-error'}`}>
              {healthInfo?.status === 'healthy' ? '● Online' : '● Offline'}
            </span>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Navigation Tabs */}
        <nav className="flex gap-2 mb-6 border-b pb-4">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                activeTab === tab.id 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Success Banner */}
        {successMessage && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg mb-6 flex items-center justify-between">
            <span>✓ {successMessage}</span>
            <button onClick={() => setSuccessMessage(null)} className="text-green-700 hover:text-green-900">✕</button>
          </div>
        )}

        {/* Error Banner */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 flex items-center justify-between">
            <span>⚠ {error}</span>
            <button onClick={() => setError(null)} className="text-red-700 hover:text-red-900">✕</button>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="ml-3 text-gray-600">Loading...</span>
          </div>
        )}

        {/* Tab Content */}
        {!loading && (
          <>
            {activeTab === 'dashboard' && (
              <Dashboard 
                healthInfo={healthInfo} 
                onNewPatient={() => openModal('patient')}
                onBookAppointment={() => openModal('appointment')}
                onCreateCampaign={() => openModal('campaign')}
              />
            )}
            {activeTab === 'patients' && (
              <PatientsList 
                patients={patients} 
                onAddPatient={() => openModal('patient')}
              />
            )}
            {activeTab === 'doctors' && <DoctorsList doctors={doctors} />}
            {activeTab === 'appointments' && (
              <AppointmentsList 
                appointments={appointments} 
                onBookAppointment={() => openModal('appointment')}
              />
            )}
            {activeTab === 'campaigns' && (
              <CampaignsList 
                campaigns={campaigns} 
                onCreateCampaign={() => openModal('campaign')}
              />
            )}
          </>
        )}
      </div>

      {/* Modals */}
      {activeModal === 'patient' && (
        <PatientFormModal 
          onClose={closeModal} 
          onSubmit={handleCreatePatient}
        />
      )}
      {activeModal === 'appointment' && (
        <AppointmentFormModal 
          onClose={closeModal} 
          onSubmit={handleCreateAppointment}
          patients={patients}
          doctors={doctors}
        />
      )}
      {activeModal === 'campaign' && (
        <CampaignFormModal 
          onClose={closeModal} 
          onSubmit={handleCreateCampaign}
        />
      )}
    </div>
  )
}

// ── Modal Components ──

function PatientFormModal({ 
  onClose, 
  onSubmit 
}: { 
  onClose: () => void
  onSubmit: (data: { first_name: string; last_name: string; phone: string; email?: string; preferred_language: string }) => void 
}) {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [language, setLanguage] = useState('en')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    await onSubmit({
      first_name: firstName,
      last_name: lastName,
      phone,
      email: email || undefined,
      preferred_language: language,
    })
    setSubmitting(false)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">Add New Patient</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700 text-2xl">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">First Name *</label>
              <input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="John"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Last Name *</label>
              <input
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Doe"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number *</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
              pattern="^\+?[0-9]{10,15}$"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="+1234567890"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="john@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Language</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="en">English</option>
              <option value="hi">Hindi</option>
              <option value="ta">Tamil</option>
            </select>
          </div>
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Create Patient'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function AppointmentFormModal({ 
  onClose, 
  onSubmit,
  patients,
  doctors,
}: { 
  onClose: () => void
  onSubmit: (data: { patient_id: string; doctor_id: string; appointment_date: string; start_time: string; reason?: string }) => void
  patients: Patient[]
  doctors: Doctor[]
}) {
  const [patientId, setPatientId] = useState('')
  const [doctorId, setDoctorId] = useState('')
  const [date, setDate] = useState('')
  const [time, setTime] = useState('')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    await onSubmit({
      patient_id: patientId,
      doctor_id: doctorId,
      appointment_date: date,
      start_time: time,
      reason: reason || undefined,
    })
    setSubmitting(false)
  }

  // Get tomorrow's date as minimum
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  const minDate = tomorrow.toISOString().split('T')[0]

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">Book Appointment</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700 text-2xl">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Patient *</label>
            <select
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select a patient</option>
              {patients.map(p => (
                <option key={p.id} value={p.id}>{p.first_name} {p.last_name} - {p.phone}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Doctor *</label>
            <select
              value={doctorId}
              onChange={(e) => setDoctorId(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select a doctor</option>
              {doctors.map(d => (
                <option key={d.id} value={d.id}>Dr. {d.first_name} {d.last_name} - {d.specialization}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date *</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
                min={minDate}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Time *</label>
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Reason for Visit</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Describe the reason for the appointment..."
            />
          </div>
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? 'Booking...' : 'Book Appointment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function CampaignFormModal({ 
  onClose, 
  onSubmit 
}: { 
  onClose: () => void
  onSubmit: (data: { name: string; campaign_type: string; message_template: Record<string, string> }) => void 
}) {
  const [name, setName] = useState('')
  const [campaignType, setCampaignType] = useState('appointment_reminder')
  const [messageEn, setMessageEn] = useState('')
  const [messageHi, setMessageHi] = useState('')
  const [messageTa, setMessageTa] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    const messageTemplate: Record<string, string> = { en: messageEn }
    if (messageHi) messageTemplate.hi = messageHi
    if (messageTa) messageTemplate.ta = messageTa
    
    await onSubmit({
      name,
      campaign_type: campaignType,
      message_template: messageTemplate,
    })
    setSubmitting(false)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">Create Campaign</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700 text-2xl">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Campaign Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="January Appointment Reminders"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Campaign Type *</label>
            <select
              value={campaignType}
              onChange={(e) => setCampaignType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="appointment_reminder">Appointment Reminder</option>
              <option value="follow_up_checkup">Follow-up Checkup</option>
              <option value="vaccination_reminder">Vaccination Reminder</option>
              <option value="general_notification">General Notification</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Message (English) *</label>
            <textarea
              value={messageEn}
              onChange={(e) => setMessageEn(e.target.value)}
              required
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Hello! This is a reminder about your appointment..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Message (Hindi)</label>
            <textarea
              value={messageHi}
              onChange={(e) => setMessageHi(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="नमस्ते! यह आपकी अपॉइंटमेंट के बारे में एक रिमाइंडर है..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Message (Tamil)</label>
            <textarea
              value={messageTa}
              onChange={(e) => setMessageTa(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="வணக்கம்! உங்கள் சந்திப்பு பற்றிய ஒரு நினைவூட்டல்..."
            />
          </div>
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Create Campaign'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Page Components ──

function Dashboard({ 
  healthInfo,
  onNewPatient,
  onBookAppointment,
  onCreateCampaign,
}: { 
  healthInfo: HealthInfo | null
  onNewPatient: () => void
  onBookAppointment: () => void
  onCreateCampaign: () => void
}) {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">System Dashboard</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-700 mb-2">System Status</h3>
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${healthInfo?.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="text-xl font-bold">{healthInfo?.status || 'Unknown'}</span>
          </div>
        </div>
        
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-700 mb-2">Database</h3>
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${healthInfo?.database ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span>{healthInfo?.database ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>
        
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-700 mb-2">Redis Cache</h3>
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${healthInfo?.redis ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span>{healthInfo?.redis ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-gray-700 mb-4">Supported Languages</h3>
        <div className="flex gap-4">
          <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 rounded-lg">
            <span className="text-2xl">🇺🇸</span>
            <span>English (en)</span>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 bg-orange-50 rounded-lg">
            <span className="text-2xl">🇮🇳</span>
            <span>Hindi (hi)</span>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 bg-purple-50 rounded-lg">
            <span className="text-2xl">🇮🇳</span>
            <span>Tamil (ta)</span>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-gray-700 mb-4">Quick Actions</h3>
        <div className="flex gap-4">
          <button onClick={onNewPatient} className="btn btn-primary">New Patient</button>
          <button onClick={onBookAppointment} className="btn btn-primary">Book Appointment</button>
          <button onClick={onCreateCampaign} className="btn btn-secondary">Create Campaign</button>
        </div>
      </div>
    </div>
  )
}

function PatientsList({ 
  patients,
  onAddPatient,
}: { 
  patients: Patient[]
  onAddPatient: () => void 
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Patients</h2>
        <button onClick={onAddPatient} className="btn btn-primary">+ Add Patient</button>
      </div>
      
      {patients.length === 0 ? (
        <div className="card text-center py-12">
          <span className="text-4xl mb-4 block">👥</span>
          <p className="text-gray-500 mb-4">No patients found</p>
          <button onClick={onAddPatient} className="btn btn-primary">Add Your First Patient</button>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Name</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Phone</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Language</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {patients.map(patient => (
                <tr key={patient.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">{patient.first_name} {patient.last_name}</td>
                  <td className="px-6 py-4">{patient.phone}</td>
                  <td className="px-6 py-4">
                    <span className="badge badge-info">{patient.preferred_language}</span>
                  </td>
                  <td className="px-6 py-4">
                    <button className="text-blue-600 hover:text-blue-800">View</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function DoctorsList({ doctors }: { doctors: Doctor[] }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Doctors</h2>
      </div>
      
      {doctors.length === 0 ? (
        <div className="card text-center py-12">
          <span className="text-4xl mb-4 block">👨‍⚕️</span>
          <p className="text-gray-500">No doctors found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {doctors.map(doctor => (
            <div key={doctor.id} className="card">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                  <span className="text-xl">👨‍⚕️</span>
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-900">
                    Dr. {doctor.first_name} {doctor.last_name}
                  </h3>
                  <p className="text-sm text-gray-500">{doctor.specialization}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {doctor.languages?.map(lang => (
                      <span key={lang} className="badge badge-info">{lang}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function AppointmentsList({ 
  appointments,
  onBookAppointment,
}: { 
  appointments: Appointment[]
  onBookAppointment: () => void 
}) {
  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, string> = {
      scheduled: 'badge-info',
      confirmed: 'badge-success',
      completed: 'badge-success',
      cancelled: 'badge-error',
      no_show: 'badge-warning',
    }
    return statusMap[status] || 'badge-info'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Appointments</h2>
        <button onClick={onBookAppointment} className="btn btn-primary">+ Book Appointment</button>
      </div>
      
      {appointments.length === 0 ? (
        <div className="card text-center py-12">
          <span className="text-4xl mb-4 block">📅</span>
          <p className="text-gray-500 mb-4">No appointments found</p>
          <button onClick={onBookAppointment} className="btn btn-primary">Book Your First Appointment</button>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Date</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Time</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Status</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {appointments.map(appt => (
                <tr key={appt.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">{appt.scheduled_date}</td>
                  <td className="px-6 py-4">{appt.scheduled_time}</td>
                  <td className="px-6 py-4">
                    <span className={`badge ${getStatusBadge(appt.status)}`}>
                      {appt.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <button className="text-blue-600 hover:text-blue-800 mr-4">Edit</button>
                    <button className="text-red-600 hover:text-red-800">Cancel</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function CampaignsList({ 
  campaigns,
  onCreateCampaign,
}: { 
  campaigns: Campaign[]
  onCreateCampaign: () => void 
}) {
  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, string> = {
      draft: 'badge-warning',
      active: 'badge-success',
      paused: 'badge-info',
      completed: 'badge-success',
    }
    return statusMap[status] || 'badge-info'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Campaigns</h2>
        <button onClick={onCreateCampaign} className="btn btn-primary">+ Create Campaign</button>
      </div>
      
      {campaigns.length === 0 ? (
        <div className="card text-center py-12">
          <span className="text-4xl mb-4 block">📢</span>
          <p className="text-gray-500 mb-4">No campaigns found</p>
          <button onClick={onCreateCampaign} className="btn btn-primary">Create Your First Campaign</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {campaigns.map(campaign => (
            <div key={campaign.id} className="card">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-gray-900">{campaign.name}</h3>
                  <p className="text-sm text-gray-500">{campaign.campaign_type}</p>
                </div>
                <span className={`badge ${getStatusBadge(campaign.status)}`}>
                  {campaign.status}
                </span>
              </div>
              <div className="text-sm text-gray-600">
                <p className="font-medium mb-2">Message Templates:</p>
                {Object.entries(campaign.message_template).map(([lang, msg]) => (
                  <div key={lang} className="mb-1">
                    <span className="badge badge-info mr-2">{lang}</span>
                    <span className="text-gray-500">{String(msg).substring(0, 50)}...</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default App
