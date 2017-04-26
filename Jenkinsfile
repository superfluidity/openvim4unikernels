pipeline {
	agent {
		label "pipeline"
	}
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
			agent any
			steps {
				unstash "deb-files"
				sh '''
					mkdir -p pool/openvim
					mv .build/*.deb pool/openvim/
					mkdir -p dists/ReleaseOne/unstable/openvim/binary-amd64/
					apt-ftparchive packages pool/openvim > dists/ReleaseOne/unstable/openvim/binary-amd64/Packages
					gzip -9fk dists/ReleaseOne/unstable/openvim/binary-amd64/Packages
					'''
				archiveArtifacts artifacts: "dists/**,pool/openvim/*.deb"
			}
		}
	}
}
