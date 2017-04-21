pipeline {
	agent any
	stages {
		stage("Build") {
			agent {
				dockerfile true
			}
			steps {
				sh 'make package'
				stash name: "deb-files", includes: ".build/*.deb"
			}
		}
		stage("Unittest") {
			agent {
				dockerfile true
			}
			steps {
				sh 'echo "UNITTEST"'
			}
		}
		stage("Repo Component") {
			steps {
				unstash "deb-files"
				sh '''
					mkdir -p pool/openvim
					mv ./build/*.deb pool/openvim/
					mkdir -p dists/$RELEASE/openvim/binary-amd64/
					apt-ftparchive packages pool/openvim > dists/$RELEASE/openvim/binary-amd64/Packages
					gzip -9fk dists/$RELEASE/openvim/binary-amd64/Packages
					'''
				archiveArtifacts artifacts: "dists/**,pool/openvim/*.deb"
			}
		}
	}
}
