/**
 * CLIENT DATA: Veronos Studio dental homepage template (sample). Every value here is a placeholder:
 * the build for a real practice swaps in that practice's own name, phone, address and links.
 */
export const client = {
  name: 'Maple Ridge Dental',
  email: 'hello@mapleridgedental.example',
  phoneForTel: '403-555-0142',
  phoneFormatted: '(403) 555-0142',
  license: '',
  address: {
    lineOne: 'Suite 200, 1234 17 Ave SW',
    lineTwo: '',
    city: 'Calgary',
    state: 'AB',
    zip: 'T2T 0A1',
    country: 'CA',
    mapLink: 'https://maps.google.com/?q=17+Ave+SW+Calgary',
  },
  socials: {
    facebook: 'https://www.facebook.com/',
    instagram: 'https://www.instagram.com/',
    google: 'https://www.google.com/maps',
  },
  domain: 'https://preview.veronosstudio.com/templates/dental/',
} as const;

export type Client = typeof client;
