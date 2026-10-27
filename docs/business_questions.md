# Business questions

Every query lives in `sql/queries/`. Once the DAG has finished, open them with either of these tools.

**Adminer (included, runs in the browser):** open http://localhost:8081 and log in:

| Field | Value |
|---|---|
| System | PostgreSQL |
| Server | `dw-db` (already filled in) |
| Username / Password | `DW_USER` / `DW_PASSWORD` from `.env` |
| Database | `datamart_dw` |

Pick the `dw` schema to browse the tables. To answer a question, go to **SQL command**, paste the content of a `.sql` file and press **Execute**.

**pgAdmin, DBeaver or any SQL client installed on your machine:** create a connection with:

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5434` (or `DW_PORT` from `.env`) |
| Database | `datamart_dw` |
| Username / Password | `DW_USER` / `DW_PASSWORD` from `.env` |

Then open a query tool and run the `.sql` files.

Amounts are in GBP (the source currency). Countries are the DataMart countries after mapping (see `decisions.md`).

## 1. Monthly net sales — `q1_monthly_net_sales.sql`

Net sales stay between £480k and £760k a month until August 2011, then climb to a peak of **£1.43M in November 2011** (Christmas season). January 2011 and December 2011 have unusually high returns; question 7 explains why. December 2011 only covers up to the 9th.

## 2. Categories — `q2_categories.sql`

| Category | Gross revenue | Return rate |
|---|---|---|
| Home | £5.67M | 4.0% |
| Other | £1.57M | 2.2% |
| Clothing | £1.28M | 1.7% |
| Stationery | £1.10M | **16.6%** |
| Electronics | £0.47M | 2.1% |
| Sports | £0.16M | 1.1% |

Home brings in the most revenue. Stationery has by far the highest return rate, but almost all of it comes from one cancelled order (question 7). Return rate only counts customer cancellations, not stock adjustments.

## 3. Top products — `q3_top_products.sql`

- **Top net revenue:** REGENCY CAKESTAND 3 TIER (£164k), WHITE HANGING HEART T-LIGHT HOLDER (£100k), PARTY BUNTING (£98k).
- **Top return rate** (products with at least 100 units sold): PAPER CRAFT, LITTLE BIRDIE (100%), ROTATING SILVER ANGELS T-LIGHT HLDR (99%), MEDIUM CERAMIC TOP STORAGE JAR (95%). The chandelier T-light holder line (ivory, flowers, beaded) also shows up with 56–66%.

## 4. Countries — `q4_countries.sql`

| Country | Invoices | Share | Average ticket |
|---|---|---|---|
| Colombia | 17,957 | 90.8% | £494 |
| Mexico | 1,016 | 5.1% | £917 |
| Peru | 800 | 4.0% | £567 |

Colombia concentrates almost all transactions, but Mexico's average ticket is almost double. Mexico mostly holds the European customers of the source data, which tend to buy in bulk.

## 5. Identified customers vs. guests — `q5_identified_vs_guest.sql`

| Type | Invoices | Revenue share | Average ticket | Lines per invoice | Price per unit |
|---|---|---|---|---|---|
| Identified | 18,402 | 85.3% | £475 | 21 | £1.70 |
| Guest | 1,371 | 14.7% | £1,101 | 96 | £3.60 |

Guest invoices are few but big: more than twice the ticket and about 4x the lines per invoice, at a higher unit price. They look like large orders placed without an account, so leaving them out would have hidden 15% of revenue.

## 6. Descriptions and product codes — `q6_descriptions.sql`

- **3,911** distinct product codes were loaded (3,958 in the raw data, including non-product codes like `POST`).
- **566** products have more than one description. Most of the extra versions are warehouse notes typed into the description field ("found", "wrongly coded 23343", "damaged"), not real name changes.

## 7. Recommendation for the product team — `q7_recommendation.sql`

**Add an approval step for very large orders before they're invoiced.**

Two single orders explain more than half of all cancelled revenue:

| Cancelled invoice | Product | Units | Amount | Share of all cancellations |
|---|---|---|---|---|
| C581484 (Dec 9, 2011) | PAPER CRAFT, LITTLE BIRDIE | 80,995 | £168,470 | 35.4% |
| C541433 (Jan 18, 2011) | MEDIUM CERAMIC TOP STORAGE JAR | 74,215 | £77,184 | 16.2% |

Both were invoiced and fully cancelled, inflating gross sales in those months and making Stationery look like the worst category for returns. A rule like "orders over 10,000 units of one product need manual approval" would have caught both, cutting cancelled revenue by about **52%** (£245k).

As a second, smaller action: review the chandelier T-light holder line, which has 56–66% of its units returned across three variants and is the clearest product-quality signal in the data.
