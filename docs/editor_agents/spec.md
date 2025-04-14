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

### Authorization

Historically Editor Agents have utilised a service account that serves all requests to the endpoint but we now offer user agents where we pass credentials from the front end to the agent that allow the agent to act as that user.

This allows much better control where the agent administrator can be much more confident around the security and Authorization of their agent. Additionally you can get more better granularity around actions understanding who requested whatnot.

If you are interested in this functionality, firstly note that you can get it automatically via the library. Whether using the GCP method or the FastAPI method, our library will inspect the headers on the request to see whether the credentials have been provided and if so, will use those credentials otherwise it will fall back to using the provided credentials. Note you can configure whether we fallback or not.

If you are interested in the gory details / implementing your own authenticated agent, please read on. We would strongly advise that end-users use the `encord-agents` library if they are interested in the Authenticated methodology as it is complicated and great care has been to ensure that we make it as intuitive and easily usable as possible.

What we do:
Following [RFC-6750](https://www.rfc-editor.org/rfc/rfc6750), we create an encrypted JWT from our Encord backend which we pass to the frontend and then pass via the Bearer token scheme to the Agent in the request from the Encord platform.
We then take the JWT from the platform request and use that as authorisation for the lifetime of this request from the frontend. As is, we do not provide the public key for the JWT and so you can't interact with it or use it as a mechanism for finger-printing the user. If you are interested in this use-case, please contact the encord team.

