/**
 * Backend API client.
 */
import axios, { AxiosInstance } from 'axios';
import { config } from '../config';
import { logger } from '../utils/logger';

export class BackendClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: config.backendUrl,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor
    this.client.interceptors.request.use((req) => {
      logger.debug('backend_request', {
        method: req.method,
        url: req.url,
      });
      return req;
    });

    // Response interceptor
    this.client.interceptors.response.use(
      (res) => res,
      (error) => {
        logger.error('backend_error', {
          url: error.config?.url,
          status: error.response?.status,
          message: error.message,
        });
        throw error;
      }
    );
  }

  // Health
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.client.get('/api/health');
      return response.status === 200;
    } catch {
      return false;
    }
  }

  // Patients
  async getPatientByPhone(phone: string): Promise<any> {
    const response = await this.client.get(`/api/patients/phone/${phone}`);
    return response.data;
  }

  async createPatient(data: {
    firstName: string;
    lastName: string;
    phone: string;
    language?: string;
  }): Promise<any> {
    const response = await this.client.post('/api/patients', {
      first_name: data.firstName,
      last_name: data.lastName,
      phone: data.phone,
      preferred_language: data.language || 'en',
    });
    return response.data;
  }

  // Doctors
  async searchDoctors(
    specialty?: string,
    language?: string
  ): Promise<any[]> {
    const params = new URLSearchParams();
    if (specialty) params.set('specialization', specialty);
    if (language) params.set('language', language);

    const response = await this.client.get(`/api/doctors?${params}`);
    return response.data;
  }

  async getDoctorAvailability(
    doctorId: string,
    date: string
  ): Promise<any> {
    const response = await this.client.get(
      `/api/doctors/${doctorId}/availability/${date}`
    );
    return response.data;
  }

  // Appointments
  async bookAppointment(data: {
    patientId: string;
    doctorId: string;
    date: string;
    time: string;
    reason?: string;
    language?: string;
  }): Promise<any> {
    const response = await this.client.post('/api/appointments', {
      patient_id: data.patientId,
      doctor_id: data.doctorId,
      appointment_date: data.date,
      start_time: data.time,
      reason: data.reason,
      language_used: data.language,
    });
    return response.data;
  }

  async cancelAppointment(
    appointmentId: string,
    reason?: string
  ): Promise<any> {
    const response = await this.client.post(
      `/api/appointments/${appointmentId}/cancel`,
      null,
      { params: { reason } }
    );
    return response.data;
  }

  async rescheduleAppointment(
    appointmentId: string,
    newDate: string,
    newTime: string
  ): Promise<any> {
    const response = await this.client.post(
      `/api/appointments/${appointmentId}/reschedule`,
      {
        new_date: newDate,
        new_time: newTime,
      }
    );
    return response.data;
  }

  // Campaigns
  async getCampaigns(status?: string): Promise<any[]> {
    const params = status ? `?status=${status}` : '';
    const response = await this.client.get(`/api/campaigns${params}`);
    return response.data;
  }

  async getCampaignStats(campaignId: string): Promise<any> {
    const response = await this.client.get(`/api/campaigns/${campaignId}/stats`);
    return response.data;
  }
}

// Singleton instance
export const backendClient = new BackendClient();
