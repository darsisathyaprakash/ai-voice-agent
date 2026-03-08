-- ============================================================
-- Voice AI Agent - PostgreSQL Schema
-- Clinical Appointment Booking System
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- PATIENTS
-- ============================================================
CREATE TABLE patients (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id     VARCHAR(64) UNIQUE,
    first_name      VARCHAR(128) NOT NULL,
    last_name       VARCHAR(128) NOT NULL,
    phone           VARCHAR(20) UNIQUE NOT NULL,
    email           VARCHAR(255),
    date_of_birth   DATE,
    gender          VARCHAR(16),
    preferred_language VARCHAR(8) DEFAULT 'en',  -- en, hi, ta
    medical_record_number VARCHAR(64) UNIQUE,
    preferences     JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_patients_phone ON patients(phone);
CREATE INDEX idx_patients_language ON patients(preferred_language);

-- ============================================================
-- DOCTORS
-- ============================================================
CREATE TABLE doctors (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name      VARCHAR(128) NOT NULL,
    last_name       VARCHAR(128) NOT NULL,
    specialization  VARCHAR(128) NOT NULL,
    department      VARCHAR(128),
    phone           VARCHAR(20),
    email           VARCHAR(255),
    consultation_duration_minutes INT DEFAULT 30,
    is_active       BOOLEAN DEFAULT TRUE,
    languages       TEXT[] DEFAULT ARRAY['en'],
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_doctors_specialization ON doctors(specialization);
CREATE INDEX idx_doctors_active ON doctors(is_active) WHERE is_active = TRUE;

-- ============================================================
-- DOCTOR SCHEDULE (Weekly recurring slots)
-- ============================================================
CREATE TABLE doctor_schedule (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doctor_id       UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    day_of_week     INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6), -- 0=Monday
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    is_available    BOOLEAN DEFAULT TRUE,
    slot_duration_minutes INT DEFAULT 30,
    max_patients    INT DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_time_range CHECK (start_time < end_time)
);

CREATE INDEX idx_schedule_doctor ON doctor_schedule(doctor_id);
CREATE INDEX idx_schedule_day ON doctor_schedule(day_of_week);

-- ============================================================
-- APPOINTMENTS
-- ============================================================
CREATE TYPE appointment_status AS ENUM (
    'scheduled',
    'confirmed',
    'in_progress',
    'completed',
    'cancelled',
    'no_show',
    'rescheduled'
);

CREATE TABLE appointments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id       UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    appointment_date DATE NOT NULL,
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    status          appointment_status DEFAULT 'scheduled',
    reason          TEXT,
    notes           TEXT,
    language_used   VARCHAR(8),
    booking_source  VARCHAR(32) DEFAULT 'voice_agent',
    cancelled_at    TIMESTAMPTZ,
    cancellation_reason TEXT,
    rescheduled_from UUID REFERENCES appointments(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT no_past_booking CHECK (
        appointment_date >= CURRENT_DATE
    ),
    CONSTRAINT valid_appointment_time CHECK (start_time < end_time)
);

CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_doctor ON appointments(doctor_id);
CREATE INDEX idx_appointments_date ON appointments(appointment_date);
CREATE INDEX idx_appointments_status ON appointments(status);
CREATE UNIQUE INDEX idx_no_double_booking ON appointments(doctor_id, appointment_date, start_time)
    WHERE status NOT IN ('cancelled', 'rescheduled');

-- ============================================================
-- CAMPAIGNS
-- ============================================================
CREATE TYPE campaign_type AS ENUM (
    'appointment_reminder',
    'follow_up_checkup',
    'vaccination_reminder',
    'general_notification'
);

CREATE TYPE campaign_status AS ENUM (
    'draft',
    'active',
    'paused',
    'completed',
    'cancelled'
);

CREATE TABLE campaigns (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(256) NOT NULL,
    campaign_type   campaign_type NOT NULL,
    status          campaign_status DEFAULT 'draft',
    message_template JSONB NOT NULL,  -- Templates per language
    target_criteria JSONB DEFAULT '{}',
    scheduled_at    TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_by      VARCHAR(128),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- CAMPAIGN TASKS (Individual outbound calls)
-- ============================================================
CREATE TYPE task_status AS ENUM (
    'pending',
    'in_progress',
    'completed',
    'failed',
    'skipped'
);

CREATE TABLE campaign_tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    appointment_id  UUID REFERENCES appointments(id),
    status          task_status DEFAULT 'pending',
    attempts        INT DEFAULT 0,
    max_attempts    INT DEFAULT 3,
    last_attempt_at TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    response_summary TEXT,
    outcome         JSONB DEFAULT '{}',
    scheduled_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tasks_campaign ON campaign_tasks(campaign_id);
CREATE INDEX idx_tasks_status ON campaign_tasks(status);
CREATE INDEX idx_tasks_scheduled ON campaign_tasks(scheduled_at) WHERE status = 'pending';

-- ============================================================
-- CONVERSATION LOGS (for analytics)
-- ============================================================
CREATE TABLE conversation_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      VARCHAR(128) NOT NULL,
    patient_id      UUID REFERENCES patients(id),
    direction       VARCHAR(16) DEFAULT 'inbound', -- inbound / outbound
    language        VARCHAR(8),
    duration_seconds INT,
    turns           INT DEFAULT 0,
    tool_calls      JSONB DEFAULT '[]',
    latency_metrics JSONB DEFAULT '{}',
    outcome         VARCHAR(64),
    transcript      JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_convlogs_session ON conversation_logs(session_id);
CREATE INDEX idx_convlogs_patient ON conversation_logs(patient_id);

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_doctors_updated_at
    BEFORE UPDATE ON doctors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_appointments_updated_at
    BEFORE UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_campaigns_updated_at
    BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_campaign_tasks_updated_at
    BEFORE UPDATE ON campaign_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- CHECK AVAILABILITY FUNCTION
-- ============================================================
CREATE OR REPLACE FUNCTION check_slot_availability(
    p_doctor_id UUID,
    p_date DATE,
    p_start_time TIME,
    p_end_time TIME
) RETURNS BOOLEAN AS $$
DECLARE
    conflicts INT;
    day_of_week INT;
    schedule_exists BOOLEAN;
BEGIN
    -- Check if date is not in the past
    IF p_date < CURRENT_DATE THEN
        RETURN FALSE;
    END IF;
    
    -- Get day of week (0=Monday in PostgreSQL with EXTRACT ISODOW - 1)
    day_of_week := EXTRACT(ISODOW FROM p_date) - 1;
    
    -- Check if doctor has schedule for this day
    SELECT EXISTS(
        SELECT 1 FROM doctor_schedule
        WHERE doctor_id = p_doctor_id
        AND doctor_schedule.day_of_week = day_of_week
        AND is_available = TRUE
        AND start_time <= p_start_time
        AND end_time >= p_end_time
    ) INTO schedule_exists;
    
    IF NOT schedule_exists THEN
        RETURN FALSE;
    END IF;
    
    -- Check for conflicting appointments
    SELECT COUNT(*) INTO conflicts
    FROM appointments
    WHERE doctor_id = p_doctor_id
    AND appointment_date = p_date
    AND status NOT IN ('cancelled', 'rescheduled')
    AND (
        (start_time <= p_start_time AND end_time > p_start_time)
        OR (start_time < p_end_time AND end_time >= p_end_time)
        OR (start_time >= p_start_time AND end_time <= p_end_time)
    );
    
    RETURN conflicts = 0;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- GET AVAILABLE SLOTS FUNCTION
-- ============================================================
CREATE OR REPLACE FUNCTION get_available_slots(
    p_doctor_id UUID,
    p_date DATE,
    p_slot_duration_minutes INT DEFAULT 30
) RETURNS TABLE(slot_start TIME, slot_end TIME) AS $$
DECLARE
    day_of_week INT;
    schedule RECORD;
    current_slot TIME;
    slot_end_time TIME;
BEGIN
    day_of_week := EXTRACT(ISODOW FROM p_date) - 1;
    
    FOR schedule IN
        SELECT start_time, end_time
        FROM doctor_schedule
        WHERE doctor_id = p_doctor_id
        AND doctor_schedule.day_of_week = day_of_week
        AND is_available = TRUE
    LOOP
        current_slot := schedule.start_time;
        
        WHILE current_slot + (p_slot_duration_minutes || ' minutes')::INTERVAL <= schedule.end_time LOOP
            slot_end_time := current_slot + (p_slot_duration_minutes || ' minutes')::INTERVAL;
            
            -- Check if slot is available
            IF check_slot_availability(p_doctor_id, p_date, current_slot, slot_end_time) THEN
                slot_start := current_slot;
                slot_end := slot_end_time;
                RETURN NEXT;
            END IF;
            
            current_slot := slot_end_time;
        END LOOP;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- SEED DATA FOR DEVELOPMENT
-- ============================================================
INSERT INTO doctors (first_name, last_name, specialization, department, consultation_duration_minutes, languages)
VALUES 
    ('Priya', 'Sharma', 'cardiologist', 'Cardiology', 30, ARRAY['en', 'hi']),
    ('Rajesh', 'Kumar', 'dermatologist', 'Dermatology', 20, ARRAY['en', 'hi', 'ta']),
    ('Ananya', 'Reddy', 'general_physician', 'General Medicine', 15, ARRAY['en', 'ta']),
    ('Vikram', 'Patel', 'orthopedic', 'Orthopedics', 30, ARRAY['en', 'hi']),
    ('Lakshmi', 'Nair', 'pediatrician', 'Pediatrics', 20, ARRAY['en', 'ta'])
ON CONFLICT DO NOTHING;

-- Add schedules for doctors (Mon-Fri, 9 AM - 5 PM)
INSERT INTO doctor_schedule (doctor_id, day_of_week, start_time, end_time, slot_duration_minutes)
SELECT d.id, dow.day, '09:00'::TIME, '17:00'::TIME, d.consultation_duration_minutes
FROM doctors d
CROSS JOIN (SELECT generate_series(0, 4) AS day) dow
ON CONFLICT DO NOTHING;
-- SEED DATA
-- ============================================================

-- Seed doctors
INSERT INTO doctors (first_name, last_name, specialization, department, consultation_duration_minutes, languages) VALUES
    ('Rajesh', 'Kumar', 'cardiologist', 'Cardiology', 30, ARRAY['en', 'hi']),
    ('Priya', 'Sharma', 'dermatologist', 'Dermatology', 20, ARRAY['en', 'hi', 'ta']),
    ('Arun', 'Nair', 'orthopedic', 'Orthopedics', 30, ARRAY['en', 'ta']),
    ('Meera', 'Patel', 'general_physician', 'General Medicine', 15, ARRAY['en', 'hi']),
    ('Suresh', 'Iyer', 'neurologist', 'Neurology', 45, ARRAY['en', 'ta']),
    ('Anita', 'Singh', 'pediatrician', 'Pediatrics', 20, ARRAY['en', 'hi']);

-- Seed doctor schedules (Monday-Friday, 9 AM - 5 PM)
INSERT INTO doctor_schedule (doctor_id, day_of_week, start_time, end_time, slot_duration_minutes)
SELECT d.id, day.n, '09:00'::TIME, '13:00'::TIME, d.consultation_duration_minutes
FROM doctors d, generate_series(0, 4) AS day(n);

INSERT INTO doctor_schedule (doctor_id, day_of_week, start_time, end_time, slot_duration_minutes)
SELECT d.id, day.n, '14:00'::TIME, '17:00'::TIME, d.consultation_duration_minutes
FROM doctors d, generate_series(0, 4) AS day(n);

-- Seed patients
INSERT INTO patients (first_name, last_name, phone, preferred_language) VALUES
    ('Amit', 'Verma', '+91-9876543210', 'hi'),
    ('Lakshmi', 'Rajan', '+91-9876543211', 'ta'),
    ('John', 'Smith', '+91-9876543212', 'en');

-- ============================================================
-- FUNCTIONS
-- ============================================================

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_doctors_updated_at
    BEFORE UPDATE ON doctors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_appointments_updated_at
    BEFORE UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_campaigns_updated_at
    BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_campaign_tasks_updated_at
    BEFORE UPDATE ON campaign_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
