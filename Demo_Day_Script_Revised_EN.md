# CoJu · Revised Demo Day Script

Team: RedBeanBun
Format: approximately 5 minutes speaking plus 3 minutes of interaction.
Use the actual results on screen. Do not promise a specific restaurant, commute time, or ranking change.
Open the running app before presenting. The GitHub repository is the source code, not the application.
For this local build, use http://localhost:8501 on the same computer. Only claim public online access after deploying and testing a public URL.

## Speaker A · Problem and approach
“Hi everyone, we are Team RedBeanBun. Think about the last time you arranged dinner with friends. Deciding where to meet can take longer than deciding what to eat.

One person is near the city centre, another is across town, and a third has a limited budget. Choosing somewhere convenient for one person can leave somebody else with a much longer journey.

CoJu is our prototype for making that decision easier to inspect. The organiser enters each person's starting location, a budget and food preferences. The app compares restaurant candidates using commute fairness, average travel time, affordability, restaurant ratings and preference matching.

We do not claim to search every restaurant or guarantee the fairest place in the city. We show the strongest options among the candidates we can find and verify, with the scores visible to the user.”

## Speaker B · Demonstration
Choose ONE branch according to the current data mode.

### Live branch
“We are using Amap data for this demonstration. First, I enter specific starting places and check the returned names and addresses. If there are similar place names, I select the correct one for each person.

That step matters. A plausible-looking result is not useful if somebody's starting point is wrong. The app does not replace an unrecognised address with a demo location.

Now I select the food categories and cuisines. Selecting several cuisines means any of those choices is acceptable. Unmatched restaurants are not added just to fill three result slots.

For transport, the default is public transport first. If no public transport option is returned, a short journey may use a verified walking or cycling route. The app does not quietly switch to driving.”

[Generate once. Read the actual venue, member count, average time and time gap.]

“This is the recommendation for our current settings. The individual journey details are shown here. Missing routes are not turned into zero-minute commutes.”

### Offline branch
“For this demonstration, I am using an explicit offline example. These are three fixed Shanghai starting points and simulated restaurant and journey data. This mode demonstrates the interaction and scoring; it does not calculate journeys for arbitrary addresses.

I will choose a budget and a cuisine available in the example dataset, then generate a plan. Notice that we display only matching restaurants. If there is one suitable example, we show one rather than adding unrelated cuisines.”

[Generate the fixed example. Read the actual displayed values.]

### Continue in either mode
“Here are the five scoring components. The total depends on our chosen weights.

I can switch the priority and the app recalculates the ranking of the candidates already collected. A different priority may change the order, although it will not necessarily do so when only one candidate qualifies.

The map shows starting points and the selected restaurant. Its dashed lines are visual connections, not road navigation. The actual journey steps appear in the result panel.

We can also look for selected activities near a restaurant. In live mode, these are location-based searches. In offline mode, they are clearly labelled examples.”

## Speaker C · What we learned and next steps
“Testing revealed three important lessons.

First, transport labels must mean what they say. We corrected the city-code parameter and removed a fallback that mixed driving into public-transport results.

Second, food preferences need to affect both search and filtering. We now search all selected cuisines, recognise alternatives such as Italian and Italian-style restaurants, and avoid using unrelated venues as filler.

Third, errors should be visible. An invalid place, unavailable route or API failure should lead to an actionable message, not a convincing but unrelated answer.

The current app uses Python, Streamlit, Amap Web APIs and an explainable scoring engine. Its interface is form-based and its result text is generated from verified structured fields. A natural-language parsing function exists as an extension, but is not connected to the current interface. We are not presenting an implemented MCP integration.

Our next priorities are better place suggestions, more representative user testing and a shared planning room where friends can contribute their own starting points.

CoJu is a prototype, but its purpose is practical: help a group compare the trade-offs and choose a place together. Thank you.”

## Q&A notes
- “Is it globally optimal?” No. It compares a bounded set of retrieved candidates.
- “Are all results real?” Only the live mode uses map-service responses. Offline results are simulated and labelled.
- “What happens when a location fails?” The app asks for a more specific place and confirmation; it does not reuse sample coordinates.
- “Why might a cuisine produce no results?” Retrieval coverage, merchant tags or route availability can limit results; that does not prove the cuisine is absent from the city.
- “Does changing weights cost more API calls?” Re-ranking the collected candidates does not call the map service again.
- “Is the AI layer fully integrated?” No. Describe the current form-and-rules implementation and the reserved parsing extension accurately.

