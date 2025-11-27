# Extraction Schema Documentation

This document describes the predefined extraction schemas used by the scraper agent.

## Gym/Fitness Studio Schema

The gym schema is designed to extract comprehensive information from gym and fitness studio websites. This schema is used when `use_gym_schema: true` is set in the scrape request (enabled by default).

### When to Use

The gym schema is automatically applied when:
- `use_gym_schema: true` in the ScrapeRequest (default setting)
- No custom `extraction_schema` is provided

To disable and use auto-generated schemas instead, set `use_gym_schema: false` in your request.

### Schema Definition

Located in: `src/schemas/gym_schema.py`

#### Fields

##### 1. `gym_studio_name`
- **Type**: string
- **Required**: Yes
- **Description**: Official name of the gym or fitness studio
- **Example**: `"The Mega Gym"`

##### 2. `modalities`
- **Type**: array of strings
- **Required**: No
- **Description**: Types of sports/fitness modalities offered. The extractor will cross-reference each option in the predefined list against the webpage content and include ALL matching options found.
- **Allowed Values** (enum):
  - `"Weightlifting / strength training"`
  - `"Yoga"`
  - `"Pilates"`
  - `"Boxing"`
  - `"Barre"`
  - `"HIIT"`
  - `"Dance"`
  - `"Crossfit"`
  - `"Spin"`
  - `"Martial arts"`
  - `"HYROX"`
- **Example**: `["Weightlifting / strength training", "Yoga", "HIIT"]`

##### 3. `google_maps_link`
- **Type**: string
- **Required**: No
- **Description**: Google Maps link for the gym location
- **Example**: `"https://maps.google.com/?q=..."`

##### 4. `address`
- **Type**: object
- **Required**: No
- **Description**: Physical address of the gym
- **Properties**:
  - `street` (string, optional): Street address
  - `city` (string, optional): City
  - `state` (string, optional): State or province
  - `postal_code` (string, optional): Postal/ZIP code
  - `country` (string, optional): Country
- **Example**:
  ```json
  {
    "street": "123 Main St",
    "city": "Brampton",
    "state": "Ontario",
    "postal_code": "L6Y 1N2",
    "country": "Canada"
  }
  ```

##### 5. `hours_of_operation`
- **Type**: object
- **Required**: No
- **Description**: Business hours by day of week
- **Properties**:
  - `monday` (string, optional): Monday hours (e.g., "6:00 AM - 10:00 PM" or "Closed")
  - `tuesday` (string, optional): Tuesday hours
  - `wednesday` (string, optional): Wednesday hours
  - `thursday` (string, optional): Thursday hours
  - `friday` (string, optional): Friday hours
  - `saturday` (string, optional): Saturday hours
  - `sunday` (string, optional): Sunday hours
- **Example**:
  ```json
  {
    "monday": "5:00 AM - 11:00 PM",
    "tuesday": "5:00 AM - 11:00 PM",
    "wednesday": "5:00 AM - 11:00 PM",
    "thursday": "5:00 AM - 11:00 PM",
    "friday": "5:00 AM - 10:00 PM",
    "saturday": "7:00 AM - 8:00 PM",
    "sunday": "7:00 AM - 8:00 PM"
  }
  ```

##### 6. `phone_number`
- **Type**: string
- **Required**: No
- **Description**: Primary contact phone number
- **Example**: `"+1-905-555-0123"`

##### 7. `email`
- **Type**: string
- **Required**: No
- **Description**: Primary contact email address
- **Example**: `"info@themegagym.com"`

##### 8. `day_passes`
- **Type**: object
- **Required**: No
- **Description**: Day pass availability and pricing
- **Properties**:
  - `available` (boolean, required): Whether day passes are offered
  - `price` (string, optional): Price of day pass if available (e.g., "$25", "$20-30")
- **Example**:
  ```json
  {
    "available": true,
    "price": "$25"
  }
  ```

##### 9. `membership_tiers`
- **Type**: array of objects
- **Required**: No
- **Description**: List of membership tiers with names and prices
- **Item Properties**:
  - `name` (string, required): Membership tier name (e.g., "Basic", "Premium", "Annual")
  - `price` (string, required): Membership price (e.g., "$99/month", "$1000/year")
  - `description` (string, optional): Brief description of what's included
- **Example**:
  ```json
  [
    {
      "name": "Basic",
      "price": "$49/month",
      "description": "Access to gym equipment during off-peak hours"
    },
    {
      "name": "Premium",
      "price": "$99/month",
      "description": "24/7 access, group classes, and personal training discount"
    }
  ]
  ```

### Usage Example

#### Request
```json
{
  "url": "https://www.themegagym.ca/",
  "purpose": "Extract gym information",
  "mode": "single-page",
  "use_gym_schema": true
}
```

#### Response (Extracted Data)
```json
{
  "gym_studio_name": "The Mega Gym",
  "modalities": [
    "Weightlifting / strength training",
    "Yoga",
    "HIIT"
  ],
  "google_maps_link": "https://maps.google.com/?q=The+Mega+Gym+Brampton",
  "address": {
    "street": "123 Main Street",
    "city": "Brampton",
    "state": "Ontario",
    "postal_code": "L6Y 1N2",
    "country": "Canada"
  },
  "hours_of_operation": {
    "monday": "5:00 AM - 11:00 PM",
    "tuesday": "5:00 AM - 11:00 PM",
    "wednesday": "5:00 AM - 11:00 PM",
    "thursday": "5:00 AM - 11:00 PM",
    "friday": "5:00 AM - 10:00 PM",
    "saturday": "7:00 AM - 8:00 PM",
    "sunday": "7:00 AM - 8:00 PM"
  },
  "phone_number": "+1-905-555-0123",
  "email": "info@themegagym.com",
  "day_passes": {
    "available": true,
    "price": "$25"
  },
  "membership_tiers": [
    {
      "name": "Basic",
      "price": "$49/month",
      "description": "Gym equipment access"
    },
    {
      "name": "Premium",
      "price": "$99/month",
      "description": "All-access with classes"
    }
  ]
}
```

### Schema Storage

Even though the schema is **not returned in the API response**, it is still saved to disk for debugging and auditing purposes:

- **Location**: `{storage_path}/{session_id}/schema.json`
- **Purpose**: Debugging, auditing, and understanding what schema was used for extraction
- **Access**: Can be viewed by directly accessing the session directory on disk

### Notes

- Fields marked as **required: true** will be set to `null` if not found (not omitted)
- Fields marked as **required: false** may be omitted from the response if not found
- The `modalities` field uses a strict enum - only values from the predefined list will be extracted
- The extractor is instructed to be thorough and check the entire webpage, including navigation, headers, footers, and all content sections
- Synonyms and related terms are considered (e.g., "resistance training" matches "Weightlifting / strength training")

## Custom Schemas

You can also provide a custom schema by including an `extraction_schema` field in your ScrapeRequest:

```json
{
  "url": "https://example.com",
  "purpose": "Extract business information",
  "mode": "single-page",
  "use_gym_schema": false,
  "extraction_schema": {
    "fields": {
      "company_name": {
        "type": "string",
        "description": "Name of the company",
        "required": true
      },
      "contact_email": {
        "type": "string",
        "description": "Primary contact email",
        "required": false
      }
    }
  }
}
```

When a custom `extraction_schema` is provided, it takes precedence over the gym schema regardless of the `use_gym_schema` flag.
