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