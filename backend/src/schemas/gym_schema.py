"""Predefined schema for gym/fitness studio data extraction."""

GYM_EXTRACTION_SCHEMA = {
    "fields": {
        "gym_studio_name": {
            "type": "string",
            "description": "Official name of the gym or fitness studio",
            "required": True
        },
        "modalities": {
            "type": "array",
            "description": "Types of sports/fitness modalities offered. Select from: Weightlifting / strength training, Yoga, Pilates, Boxing, Barre, HIIT, Dance, Crossfit, Spin, Martial arts, HYROX. Include ALL that apply from this list if found on the website.",
            "required": False,
            "items": {
                "type": "string",
                "enum": [
                    "Weightlifting / strength training",
                    "Yoga",
                    "Pilates",
                    "Boxing",
                    "Barre",
                    "HIIT",
                    "Dance",
                    "Crossfit",
                    "Spin",
                    "Martial arts",
                    "HYROX"
                ]
            }
        },
        "google_maps_link": {
            "type": "string",
            "description": "Google Maps link for the gym location",
            "required": False
        },
        "address": {
            "type": "object",
            "description": "Physical address of the gym",
            "required": False,
            "properties": {
                "street": {
                    "type": "string",
                    "description": "Street address",
                    "required": False
                },
                "city": {
                    "type": "string",
                    "description": "City",
                    "required": False
                },
                "state": {
                    "type": "string",
                    "description": "State or province",
                    "required": False
                },
                "postal_code": {
                    "type": "string",
                    "description": "Postal/ZIP code",
                    "required": False
                },
                "country": {
                    "type": "string",
                    "description": "Country",
                    "required": False
                }
            }
        },
        "hours_of_operation": {
            "type": "object",
            "description": "Business hours by day of week",
            "required": False,
            "properties": {
                "monday": {
                    "type": "string",
                    "description": "Monday hours (e.g., '6:00 AM - 10:00 PM' or 'Closed')",
                    "required": False
                },
                "tuesday": {
                    "type": "string",
                    "description": "Tuesday hours",
                    "required": False
                },
                "wednesday": {
                    "type": "string",
                    "description": "Wednesday hours",
                    "required": False
                },
                "thursday": {
                    "type": "string",
                    "description": "Thursday hours",
                    "required": False
                },
                "friday": {
                    "type": "string",
                    "description": "Friday hours",
                    "required": False
                },
                "saturday": {
                    "type": "string",
                    "description": "Saturday hours",
                    "required": False
                },
                "sunday": {
                    "type": "string",
                    "description": "Sunday hours",
                    "required": False
                }
            }
        },
        "phone_number": {
            "type": "string",
            "description": "Primary contact phone number",
            "required": False
        },
        "email": {
            "type": "string",
            "description": "Primary contact email address",
            "required": False
        },
        "day_passes": {
            "type": "object",
            "description": "Day pass availability and pricing",
            "required": False,
            "properties": {
                "available": {
                    "type": "boolean",
                    "description": "Whether day passes are offered (Yes/No)",
                    "required": True
                },
                "price": {
                    "type": "string",
                    "description": "Price of day pass if available (e.g., '$25', '$20-30')",
                    "required": False
                }
            }
        },
        "membership_tiers": {
            "type": "array",
            "description": "List of membership tiers with names and prices",
            "required": False,
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Membership tier name (e.g., 'Basic', 'Premium', 'Annual')",
                        "required": True
                    },
                    "price": {
                        "type": "string",
                        "description": "Membership price (e.g., '$99/month', '$1000/year')",
                        "required": True
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of what's included",
                        "required": False
                    }
                }
            }
        }
    }
}
