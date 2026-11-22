# Energy Price Calculator (Home Assistant)

Bereken per energieleverancier (stroom en gas) de eindprijs op basis van een kale marktprijs-sensor,
zonder afhankelijk te zijn van een specifieke bron. Werkt met elke sensor die een lijst met prijzen
in een attribuut heeft (Frank Energie, Nord Pool, ENTSO-e, Tibber, EasyEnergy, ...), en valt anders terug op de state van de sensor.

Formule per prijsperiode:

    leveranciersprijs = (marktprijs + inkoopvergoeding + energiebelasting) × (1 + btw/100)

Is de bronprijs al inclusief btw, zet dan "Bronprijs is al inclusief btw" aan; de btw wordt er dan eerst uitgehaald.

## Installatie
HACS → Custom repositories → deze repo (type Integration), of kopieer `custom_components/energy_price_calculator` naar `/config/custom_components/`. Herstart HA.

## Gebruik
Instellingen → Apparaten & diensten → Integratie toevoegen → *Energy Price Calculator*. Voeg per leverancier en per soort (stroom/gas) een entry toe.
Tarieven wijzigen kan later via *Configureren* (bijv. nieuwe energiebelasting per 1 januari).

Voorbeeld Vattenfall (stroom, bron Frank Energie `sensor.frank_energie_prijzen_huidige_elektriciteit_inkoopprijs`):

| veld | waarde |
|---|---|
| Inkoopvergoeding | 0,021 |
| Energiebelasting | 0,092 |
| Btw | 21 |

Dit is gelijk aan de oude ENTSO-e template `((current_price + 0.021 + 0.092) * 1.21)`.

## Sensoren per leverancier
- Prijs (nu), met attribuut `prices` (`from`, `till`, `time`, `price`) voor grafieken zoals apexcharts-card
- Volgende prijs, laagste / hoogste / gemiddelde prijs vandaag, en laagste / hoogste / gemiddelde prijs morgen (zodra de bron de prijzen van morgen levert)

Eenheid: €/kWh (stroom) of €/m³ (gas).

## Ondersteunde prijslijst-formaten
Lijst van dicts met `from`/`start`/`time` en `price`/`value`/`total`, optioneel `till`/`end`; of lijst van `[tijd, prijs]`. Kwartier- en uurprijzen worden beide ondersteund.

## Tests
`pip install pytest && pytest` (de rekenlogica in `calc.py` is vrij van HA-imports).
