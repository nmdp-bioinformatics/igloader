# igloader

HL7(R) FHIR(R) implementation guide uploader (from IG pack tarball file).

For now, this is a very simplistic IG uploader, with no handling of the
IG pack's package.json file or server's CapabilityStatement.

Except for the requests module, this code uses only Python standard library
modules.  It uses the json module to inspect file resource types, but uploads
raw IG pack file content, in part due to limitations in the json module's
handling of decimal data types.

Usage example ...

1. Clone GitHub repo.
```
git clone https://github.com/nmdp-bioinformatics/igloader.git
cd igloader
```

2. Create Python 3 virtual environment, and activate it.
```
python3 -m venv venv
source venv/bin/activate
```

4. Install igloader module into virtual environment.
```
python setup.py install
```

5. Obtain an igpack file and upload its conformance-related content to a FHIR
server.  (Additionally, pass OAuth access/bearer token via ACCESS_TOKEN
environment variable).
```
curl http://hl7.org/implement/standards/fhir/us/core/STU3.1.1/package.tgz --output us-core-v3.1.1-package.tgz
export ACCESS_TOKEN=MySecretAccessToken
python -m igloader --igpack us-core-v3.1.1-package.tgz --target http://localhost:8080/r4
```