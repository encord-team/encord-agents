## Editor Agent specification

This defines the interface and will be useful for defining agents either via the library or writing your own implementation.

## Schema:
```typescript
type EditorAgentPayload = {
  projectHash: string;
  dataHash: string;
  frame?: number;
  objectHashes?: string[];
};
```

This aligns with the [FrameData](../reference/core.md#encord_agents.core.data_model.FrameData). Notably we use the `objectHashes: string[]` type to represent that the field is either **not present** or **present and a list of strings**.

### Test Payload

Additionally when registering your editor agent in the platform at: [Editor Agents](https://app.encord.com/agents/editor-agents?limit=10){ target="\_blank", rel="noopener noreferrer" }, you can test your agent via a test payload. We will appropriately check that your agent has access to the associated project, data item if you modify the payload, otherwise we will send a distinguished Header: `X-Encord-Editor-Agent` which will automatically respond appropriately. This allows you to test that you have deployed your agent appropriately and that your session can see the Agent (all requests to your agent are made from your browser session rather than the Encord backend) and additionally, you can test that it works on particular projects.

### Error handling

Additionally, if you make use of the `AuthorisationError` handler (via [get_encord_app](../reference/editor_agents.md#encord_agents.fastapi.cors.get_encord_app)), then we will raise appropriate errors depending on issues with the Agent. Most notably, in the event of an Authorisation issue with the Encord platform e.g., A request attempting to access a project that the agent doesn't have access too, then we will additionally include message in the body of the response:

```typescript
type EditorAgentErrorResponse = {
  message?: string;
}
```

We will display this in the platform to allow intuitive usage of your agent.