# Public electricity data

`carbon_2024.csv` contains eight observations from **Ember, Yearly Electricity Data**, downloaded on 21 September 2026. The source data are released under the **Creative Commons Attribution 4.0 International license (CC BY 4.0)**, not the repository's MIT software license.

- Publisher and dataset: https://ember-energy.org/data/yearly-electricity-data/
- Download: https://files.ember-energy.org/public-downloads/yearly_full_release_long_format.csv
- Publisher's licensing statement: https://ember-energy.org/creative-commons/
- License: https://creativecommons.org/licenses/by/4.0/
- Methodology: https://files.ember-energy.org/public-downloads/ember_electricity_data_methodology.pdf

Selection: `Year == 2024`, `Variable == CO2 intensity`, for Finland, France, Germany, Ireland, Netherlands, Poland, Spain and Sweden. The CSV preserves the source values in gCO2/kWh and records the source URL and retrieval date. `provenance.json` records the SHA-256 of the downloaded full dataset and the model transformation. The full download is not required for reproduction and is not redistributed here.

Changes relative to the source: the eight rows were selected and reformatted into a compact table. The model divides the values by 1000 and assumes 1 kWh of facility electricity per normalized service unit. Assumed seasonal multipliers are normalized to preserve each country's annual factor. The observations themselves are unchanged.

These are national electricity-generation factors with a lifecycle boundary. They are not site-specific electricity measurements, consumption-adjusted factors or certified Scope 2 factors. Demand, water, costs and other operational assumptions are constructed separately in the model. Ember does not endorse the model or its conclusions.

When redistributing the extracted data or their adaptations, retain Ember attribution, the CC BY 4.0 link, and an indication of your changes. Embedded source values in the archived instance and derived outputs retain the relevant attribution; this repository does not relicense third-party rights under MIT.
