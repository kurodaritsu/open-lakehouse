package io.lakehouse.uc;

import io.unitycatalog.server.service.credential.CredentialContext;
import io.unitycatalog.server.service.credential.aws.AwsCredentialGenerator;
import software.amazon.awssdk.services.sts.model.Credentials;

/**
 * Vends the static S3 keys, choosing the session token per caller.
 *
 * UC OSS's built-in static mode echoes the placeholder `s3.sessionToken.N` back to clients.
 * Two clients disagree about it:
 *  - SeaweedFS rejects any request carrying `X-Amz-Security-Token` (it validates the header as
 *    one of its own STS JWTs) -> MLflow's UC artifact repo, which signs with the vended token,
 *    gets InvalidAccessKeyId. It needs an EMPTY token so the SDK omits the header.
 *  - The UC Spark connector (unitycatalog-hadoop `AwsCredential`) rejects an empty token with
 *    "AWS session token is missing", even with the cred-scoped filesystem disabled.
 *
 * The only thing the server can see is the requested path, and model artifacts always live under
 * `__unitystorage/.../models/`, so: empty token for model paths, placeholder for everything else.
 * No downscoping either way, same as UC's own StaticAwsCredentialGenerator.
 *
 * Wired via `s3.credentialGenerator.0` in server.properties. Loaded with Class.forName and a
 * no-arg constructor, so the keys come from the container environment (compose passes
 * AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from .env). Remove once unitycatalog#1532 lands and
 * UC can talk to SeaweedFS's own STS via aws.masterRoleArn.
 */
public class StaticNoTokenCredentialGenerator implements AwsCredentialGenerator {
  private final String accessKeyId = require("AWS_ACCESS_KEY_ID");
  private final String secretAccessKey = require("AWS_SECRET_ACCESS_KEY");

  private static final String PLACEHOLDER_TOKEN = "not_used";

  @Override
  public Credentials generate(CredentialContext ctx) {
    boolean modelPath =
        ctx.getLocations() != null
            && ctx.getLocations().stream().anyMatch(l -> l.toString().contains("/models/"));
    return Credentials.builder()
        .accessKeyId(accessKeyId)
        .secretAccessKey(secretAccessKey)
        .sessionToken(modelPath ? "" : PLACEHOLDER_TOKEN)
        .build();
  }

  private static String require(String name) {
    String v = System.getenv(name);
    if (v == null || v.isEmpty()) {
      throw new IllegalStateException(name + " must be set for StaticNoTokenCredentialGenerator");
    }
    return v;
  }
}
