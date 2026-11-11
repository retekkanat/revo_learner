# Kestrel Telecom

Kestrel Telecom is a fictional broadband provider in the United Kingdom. It exists only for this course. Every customer, member of staff, case, address, phone number and email address that belongs to Kestrel is invented. The instructor builds Kestrel's support-case assistant in the Module 1 demonstrations, from the first model call in Week 1 to Support Assistant v3 in Week 3, and learners who choose the exercises build its parts themselves.

This page is background for learners and instructors. It isn't part of the document corpus in `documents/`, so the assistant never answers from it or cites it.

## What Kestrel sells

Kestrel sells fibre broadband to about 180,000 homes and small businesses in nine service areas. The dataset writes these areas as `KT-01` to `KT-09` instead of real postcodes. Every plan includes unlimited data, the KR-3 router and a digital voice home phone service.

| Plan | Identifier | Download speed up to | Minimum guaranteed download speed | Monthly price | Minimum term |
| --- | --- | --- | --- | --- | --- |
| Essential 80 | `essential_80` | 80 Mbps | 40 Mbps | £26.00 | 18 months |
| Fibre 300 | `fibre_300` | 300 Mbps | 150 Mbps | £34.00 | 18 months |
| Fibre 900 | `fibre_900` | 900 Mbps | 450 Mbps | £45.00 | 18 months |
| Business 500 | `business_500` | 500 Mbps | 300 Mbps | £58.00 excluding VAT | 24 months |

## Support teams

Kestrel's support work is split between three teams, and every case belongs to exactly one of them. Network operations, which isn't a support team, repairs the network and declares outages.

| Team | Identifier | What it handles | Phone |
| --- | --- | --- | --- |
| Customer care | `customer_care` | Orders, moving home, cancellations, complaints and general questions | 01632 960100 |
| Technical support | `technical_support` | Faults, slow speeds, routers, engineer visits and outages | 01632 960150 |
| Billing | `billing` | Bills, payments, refunds and credits | 01632 960170 |

Business customers call a separate business support line on 01632 960200. Customers can also email help@kestrel.example.

## Service levels

Kestrel repairs a fault on a home plan by the end of the second working day after the customer reports it. Customers registered for priority support have a target of the end of the next calendar day, and Business 500 customers have a target of the end of the next working day. When Kestrel misses a target on a home plan, it credits £8.00 for each calendar day until the service is restored. Business 500 customers receive a service credit of £15.00 for each working day instead.

Technical support responds to a reported fault within 4 hours. Customer care responds within 1 working day, and billing responds within 2 working days.

## The four user roles

The support assistant serves four kinds of user. The course uses one synthetic user for each role, defined in `users.json`.

| Role | Identifier | What the user can do |
| --- | --- | --- |
| Customer | `customer` | Asks questions about Kestrel's services and looks up the cases that belong to their own account. |
| First-line agent | `first_line_agent` | Looks up the cases that their team owns, drafts replies to customers, and gives goodwill credits of up to £20.00 on a case. |
| Supervisor | `supervisor` | Does everything a first-line agent can, and approves goodwill credits of up to £150.00 on cases that their team owns. |
| Auditor | `auditor` | Reads every case and the record of who did what, but can't draft replies or give credits. |

The first-line agent and the supervisor both work in technical support, so a billing or customer care case is outside their scope.
