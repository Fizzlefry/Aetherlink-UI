import Keycloak from "keycloak-js";

const keycloak = new Keycloak({
    url: "http://localhost:8180",
    realm: "aetherlink",
    clientId: "aetherlink-crm-ui",
});

export default keycloak;
