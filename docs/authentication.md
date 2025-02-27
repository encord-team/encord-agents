To interact with the Encord platform programmatically, you must authenticate each time you run a script that uses the Encord SDK.

Follow these steps:

1. Ensure you have an Encord account. If not, [register here][register]{ target="\_blank", rel="noopener noreferrer" }.
2. Create a public and private SSH key for authentication by following [this documentation][docs-auth]{ target="\_blank", rel="noopener noreferrer" }.  
   > 💡 We recommend creating a [service account][docs-service-account]{ target="\_blank", rel="noopener noreferrer" } to be used with agents.
3. Set one of the following environment variables in the environment where you plan to run your agents:
      - `ENCORD_SSH_KEY`: The raw content of your private key file.
      - `ENCORD_SSH_KEY_FILE`: The absolute path to your private key file.



[register]: https://app.encord.com/register
[docs-ssh-key-access]: https://docs.encord.com/sdk-documentation/sdk-references/EncordUserClient#create-with-ssh-private-key
[docs-auth]: https://docs.encord.com/platform-documentation/Annotate/annotate-api-keys
[docs-service-account]: https://docs.encord.com/platform-documentation/GettingStarted/getting-started-service-accounts