To interact with the Encord platform, you need to authenticate.
Please, follow these steps:

1. Ensure that you have an Encord account. If you don't, you can [register here][register]{ target="\_blank", rel="noopener noreferrer" }.
2. Follow [this documentation][docs-auth]{ target="\_blank", rel="noopener noreferrer" } to obtain a public and private ssh key.
   > 💡 Consider creating a service accounte for the purpose of creating agents.
3. In the environment that you plan to run your agents, set either of these two environment variables:
   - `ENCORD_SSH_KEY`: Containing the raw private key file content
   - `ENCORD_SSH_KEY_FILE`: Containing the absolute path to the private key file

If none of the env variables are set, the code will cast a pydantic validation error the first time it needs the ssh key.

> ℹ️ Effectively, [this part][docs-ssh-key-access]{ target="\_blank", rel="noopener noreferrer" } of the `encord` SDK is used to perform authentication.

[register]: https://app.encord.com/register
[docs-ssh-key-access]: https://docs.encord.com/sdk-documentation/sdk-references/EncordUserClient#create-with-ssh-private-key
[docs-auth]: https://docs.encord.com/platform-documentation/Annotate/annotate-api-keys
