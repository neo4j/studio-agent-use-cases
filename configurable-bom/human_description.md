# Configurable Bill of Materials

For manufacturers whose products are ordered rather than picked off a shelf:
a way to hold every variant a product could be as one connected structure, and
resolve a single buildable one from it against the rules that apply.

## Overview

### The industry

In configure-to-order and engineer-to-order manufacturing, the bill of materials
is not a list. It is a superset. A mountain bike, an industrial pump, a delivery
van and a switchgear cabinet are all sold as a family of options, and what
actually gets built is decided per order — sometimes per customer conversation.

The people responsible for this sit between sales and the shop floor:

- **Product and design engineers**, who own the option structure itself and
  decide which combinations are engineeringly valid.
- **Configuration and order engineers**, who turn a customer specification into
  a buildable release, and who are the ones who find out when it cannot be done.
- **Cost engineers and procurement**, who need the cost and mass of a variant
  before anyone commits to a price or a shipping class.
- **Compliance and quality**, who must be able to show, for a specific unit
  shipped, which components were in it and why they were permitted.

What makes the work hard is that the options are not independent. A larger wheel
forces a different rim and a different tire. A material banned under one market's
substance restrictions has to disappear from every assembly it appears in,
including the ones nobody was thinking about.

So the combinations grow multiplicatively, while the *valid* combinations are a
small and irregularly shaped subset of them — and the rules defining that subset
live in spreadsheets, in configurator code, and in a handful of people's heads.

The usual failure is quiet. A specification is accepted, the order is
acknowledged, and the contradiction surfaces on the line, in a supplier lead
time, or at conformity assessment.

### What it helps with

The reference ontology holds the option structure and the choices as first-class
things, so that resolving a variant is a traversal that prunes as it goes rather
than a generate-and-test over combinations.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| A customer specification is accepted that cannot actually be built | Decisions that no permitted option satisfies are reported explicitly, by name and by where they sit in the structure, instead of surfacing later as a shortage or a production stop |
| Rules are enforced late, after a combination has been assembled and priced | Each choice is filtered as the structure is walked, so rejected combinations are never formed and never have to be tested |
| A specification leaves genuine choices open and someone picks by habit | Whole sub-branches are costed and weighed and compared against stated priorities, so the trade-off between a cheaper option and a lighter one is made once, explicitly, and is visible afterwards |
| One option quietly changes what is needed several levels down | Choosing an option brings in the decisions nested beneath it, and quantities multiply down the path, so a choice two levels up is correctly reflected in the count of the smallest component |
| Cost and mass of a variant are not known until late | Both roll up over the resolved structure from per-unit values on the components, giving a figure as soon as the variant is resolved |
| A restricted material has to be removed across an entire product family | A restriction is expressed once against the category of decision it governs, and applies wherever that category appears, rather than being edited into each place separately |
| Nobody can reconstruct why a shipped unit contained what it contained | Each resolution is recorded against a named variant, so many resolutions coexist over one structure and each remains inspectable |

## Ontology

The reference ontology separates three things that are usually blurred together:
what a product is *made of*, what still has to be *decided* about it, and what
was actually *chosen* for one particular variant.

The structure is a hierarchy of products, assemblies and components, but with
decision points standing in it as entities in their own right. Wherever a choice
exists, a configuration group sits between the parent and the alternatives, and
carries the category the choice belongs to.

That is what makes rules expressible: a restriction is written against a
category, not against a place in the hierarchy, so it reaches every decision of
that kind. An alternative may be a single component or an entire sub-assembly,
and choosing a sub-assembly brings in the decisions nested inside it — which is
how a wheel size choice reaches down to rims and tires.

Resolution never rewrites the structure. It records selections as a separate
layer of links, each tagged with a variant name, so one structure can carry many
resolved variants at once and each can be read back, costed, or discarded on its
own.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Product` | A configurable end product whose bill of materials is not fixed until a variant is resolved. The root of the configurable structure |
| `Assembly` | A reusable sub-assembly grouping fixed components and further decisions. May sit directly beneath the product, or be offered as one of the alternatives of a decision |
| `ConfigGroup` | A single configuration decision: a named set of interchangeable alternatives, exactly one of which is chosen for any given variant |
| `Part` | A procured or manufactured component that is not broken down further. The leaves of a resolved bill of materials, and the only entities carrying cost and mass |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Product` | `productId` | String | Unique identifier for the product in the engineering catalog, stable across revisions of the configurable structure |
| `Product` | `description` | String | Human-readable name or specification, as an engineer would recognise it on a drawing or in a catalog |
| `Assembly` | `assemblyId` | String | Unique identifier for the assembly in the engineering catalog, stable across revisions |
| `Assembly` | `description` | String | Human-readable name or specification, as an engineer would recognise it on a drawing or in a catalog |
| `Assembly` | `wheelSize` | String | Option attribute. Nominal wheel diameter in inches, written as a decimal string so permitted and excluded lists match it exactly. Present only on assemblies offered as alternatives of a decision that varies by wheel size |
| `ConfigGroup` | `configGroupId` | String | Unique identifier for the decision in the engineering catalog, stable across revisions |
| `ConfigGroup` | `category` | String | The kind of decision this is, as a lower-case hyphenated term. Rules are matched to decisions by this value, so two decisions sharing a category are governed by the same rule |
| `ConfigGroup` | `optionProperty` | String | The name of the property, carried by each alternative, whose value distinguishes the alternatives from one another. Records what a rule on this category should filter on |
| `ConfigGroup` | `description` | String | Human-readable explanation of the decision, phrased as it would be presented to whoever is specifying the product |
| `Part` | `partId` | String | Unique identifier for the component in the engineering catalog, stable across revisions |
| `Part` | `description` | String | Human-readable name or specification, as an engineer would recognise it on a drawing or in a catalog |
| `Part` | `cost` | Float | Purchase cost of one unit, in the catalog's base currency. Per unit, not per assembly — a rollup multiplies it by the quantities on the path down from the product |
| `Part` | `weight` | Float | Mass of one unit in kilograms. Per unit, not per assembly — a rollup multiplies it by the quantities on the path down from the product |
| `Part` | `material` | String | Option attribute. The material the component is made from, as a catalog term matched exactly by permitted and excluded lists. Present only on components offered as alternatives of a decision that varies by material |
| `Part` | `pattern` | String | Option attribute. The tread pattern of a tire, as a catalog term matched exactly. Present only on components offered as alternatives of a decision that varies by tread |
| `Part` | `gearSystem` | String | Option attribute. The gearing standard a drivetrain component belongs to. Components sharing a value are compatible with one another, which is how one rule keeps several matched components in step |
| `Part` | `color` | String | Option attribute. The finish colour, as a catalog term matched exactly. Present only on components offered as alternatives of a decision that varies by colour |
| `Part` | `brakeType` | String | Option attribute. The braking technology the component implements. Present only on components offered as alternatives of a decision that varies by braking technology |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `REQUIRES` | `Product` → `Assembly` | Building the product requires this sub-assembly, in the quantity carried on the relationship. A product may require many assemblies, or none; an assembly may be required by more than one product |
| `REQUIRES` | `Product` → `ConfigGroup` | A decision must be made at product level before the bill of materials is complete, and the chosen alternative is needed in the quantity carried on the relationship. Each decision is required by exactly one product or assembly |
| `REQUIRES` | `Assembly` → `ConfigGroup` | A decision must be made within the assembly before it is complete, and the chosen alternative is needed in the quantity carried on the relationship. Each decision is required by exactly one product or assembly |
| `HAS_PART` | `Assembly` → `Part` | A component always present in the assembly, in the quantity carried on the relationship — no decision attached, so it appears in every variant reaching the assembly. The same component may be used by more than one assembly |
| `HAS_OPTION` | `ConfigGroup` → `Part` | Offers a component as one of the interchangeable alternatives of the decision. A decision offers two or more, of which resolution keeps exactly one. Carries no quantity — how many are needed is stated on the requirement into the decision |
| `HAS_OPTION` | `ConfigGroup` → `Assembly` | Offers a whole sub-assembly as one of the alternatives, so choosing it brings in every decision nested beneath it. A decision offers two or more, of which resolution keeps exactly one |
| `RESOLVED_LINK` | `Product` → `Assembly` | For one named variant, the product's requirement for this assembly was selected and survived. At most one per variant between the same pair |
| `RESOLVED_LINK` | `Product` → `ConfigGroup` | For one named variant, this product-level decision was reached and at least one alternative below it survived. More than one indicates a decision the rules left open |
| `RESOLVED_LINK` | `Assembly` → `ConfigGroup` | For one named variant, a decision nested inside the assembly was reached and at least one alternative below it survived. More than one indicates a decision the rules left open |
| `RESOLVED_LINK` | `Assembly` → `Part` | For one named variant, a fixed component of the assembly is present in the resolved bill of materials. At most one per variant between the same pair |
| `RESOLVED_LINK` | `ConfigGroup` → `Part` | For one named variant, this component is a surviving alternative. Exactly one is a decision made; more than one is a decision still open; none at all is a decision the rules could not satisfy |
| `RESOLVED_LINK` | `ConfigGroup` → `Assembly` | For one named variant, this sub-assembly is a surviving alternative, bringing every decision nested beneath it into the variant. Exactly one is a decision made; more than one is still open; none at all could not be satisfied |

### Relationship properties

`REQUIRES` carries the same two properties on all three of the pairs above, and
`RESOLVED_LINK` the same three on all six. `HAS_OPTION` carries none.

| Relationship | Property | Type | What it holds |
| ------------ | -------- | ---- | ------------- |
| `REQUIRES` | `qty` | Integer | Number of the required assembly or chosen alternative needed per one of the parent. Multiplied along the path when costing or weighing a resolved variant |
| `REQUIRES` | `note` | String | Free-text engineering note explaining why the requirement exists or how the quantity was arrived at |
| `HAS_PART` | `qty` | Integer | Number of the component needed per one of the assembly. Multiplied along the path when costing or weighing a resolved variant |
| `RESOLVED_LINK` | `idVariant` | String | Name of the resolved variant this selection belongs to, so several variants can coexist over one structure |
| `RESOLVED_LINK` | `relType` | String | The kind of structural relationship the selection was resolved from, copied at resolution time, so a resolved bill of materials can be read back without re-walking the configurable structure |
| `RESOLVED_LINK` | `qty` | Integer | Quantity copied from the structural relationship the selection was resolved from, per one of the source entity. Absent where the source carried none, in which case a rollup treats it as one |
