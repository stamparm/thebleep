class Thebleep < Formula
  include Language::Python::Virtualenv

  desc "Corrects your previous console command"
  homepage "https://github.com/stamparm/thebleep"
  url "https://files.pythonhosted.org/packages/04/b7/33b948d40329a1feb70379d8ac730dbabc6a7c1a9cfbfaa66758db9751de/thebleep-4.0.4.tar.gz"
  sha256 "dd5e80980dd5ae1c104701f914a9750f88990b9ec56331b6ca2ba78e687df93f"
  license "MIT"

  depends_on "python@3.13"

  resource "psutil" do
    url "https://files.pythonhosted.org/packages/aa/c6/d1ddf4abb55e93cebc4f2ed8b5d6dbad109ecb8d63748dd2b20ab5e57ebe/psutil-7.2.2.tar.gz"
    sha256 "0746f5f8d406af344fd547f1c8daa5f5c33dbc293bb8d6a16d80b4bb88f59372"
  end

  resource "pyte" do
    url "https://files.pythonhosted.org/packages/ab/ab/b599762933eba04de7dc5b31ae083112a6c9a9db15b01d3109ad797559d9/pyte-0.8.2.tar.gz"
    sha256 "5af970e843fa96a97149d64e170c984721f20e52227a2f57f0a54207f08f083f"
  end

  resource "wcwidth" do
    url "https://files.pythonhosted.org/packages/f0/b4/7830542634bb2d3e62aa3b586a72d5b3b6c91c3168929e7000ef3fed041d/wcwidth-0.9.2.tar.gz"
    sha256 "ae0ef90b90f6af38b54f1fe6d58662ec33b3cb4b8391958a62416d654231727b"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/thebleep --version 2>&1")
    assert_equal "echo hi",
                 shell_output("env TB_SHELL=bash #{bin}/thebleep --yes ehco hi 2>/dev/null")
  end
end
