import Foundation
import Photos
import AppKit
import ImageIO
import UniformTypeIdentifiers

func emit(_ values: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: values) else { return }
    FileHandle.standardOutput.write(data); FileHandle.standardOutput.write(Data([10]))
}
final class Bridge: NSObject, PHPhotoLibraryChangeObserver {
    let source: URL, destination: URL
    var asset: PHAsset?
    var lastDate: Date?
    var exporting = false
    var pending = false
    init(source: String, destination: String) {
        self.source = URL(fileURLWithPath: source); self.destination = URL(fileURLWithPath: destination)
    }
    func start() {
        PHPhotoLibrary.requestAuthorization(for: .readWrite) { status in
            guard status == .authorized || status == .limited else {
                emit(["error": "Allow Clarette access to Photos to send and receive this portrait."]); exit(2)
            }
            var identifier: String?
            PHPhotoLibrary.shared().performChanges({
                identifier = PHAssetChangeRequest.creationRequestForAssetFromImage(atFileURL: self.source)?.placeholderForCreatedAsset?.localIdentifier
            }) { success, error in
                guard success, let id = identifier, let asset = PHAsset.fetchAssets(withLocalIdentifiers: [id], options: nil).firstObject else {
                    emit(["error": error?.localizedDescription ?? "Photos could not import this portrait."]); exit(3)
                }
                DispatchQueue.main.async {
                    self.asset = asset; self.lastDate = asset.modificationDate
                    PHPhotoLibrary.shared().register(self)
                    emit(["imported": id])
                    // Opening the imported asset leaves editing to Photos, including Extend/Reframe.
                    NSWorkspace.shared.open(URL(fileURLWithPath: "/System/Applications/Photos.app"))
                }
            }
        }
    }
    func photoLibraryDidChange(_ change: PHChange) {
        DispatchQueue.main.async {
            guard let old = self.asset, let details = change.changeDetails(for: old) else { return }
            guard let updated = details.objectAfterChanges else { emit(["error":"The Photos copy was removed."]); exit(0) }
            self.asset = updated
            guard details.assetContentChanged || updated.modificationDate != self.lastDate else { return }
            self.lastDate = updated.modificationDate
            self.exportCurrent()
        }
    }
    func exportCurrent() {
        guard let asset else { return }
        if exporting { pending = true; return }
        exporting = true
        let options = PHImageRequestOptions(); options.version = .current; options.deliveryMode = .highQualityFormat; options.isNetworkAccessAllowed = true
        PHImageManager.default().requestImageDataAndOrientation(for: asset, options: options) { data, _, _, info in
            DispatchQueue.main.async {
                defer { self.exporting = false; if self.pending { self.pending = false; self.exportCurrent() } }
                guard let data else { emit(["error": "Photos could not return the saved image. Keep Photos open and try saving again."]); return }
                do {
                    guard let source = CGImageSourceCreateWithData(data as CFData, nil),
                          let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [kCGImageSourceCreateThumbnailFromImageAlways:true, kCGImageSourceCreateThumbnailWithTransform:true, kCGImageSourceThumbnailMaxPixelSize:max(asset.pixelWidth,asset.pixelHeight)] as CFDictionary) else { throw NSError(domain:"ClarettePhotos",code:1,userInfo:[NSLocalizedDescriptionKey:"Could not decode the saved Photos image."]) }
                    let png = NSMutableData()
                    guard let output = CGImageDestinationCreateWithData(png, UTType.png.identifier as CFString, 1, nil) else { return }
                    CGImageDestinationAddImage(output, image, nil)
                    guard CGImageDestinationFinalize(output) else { return }
                    let file = self.destination.appendingPathComponent(UUID().uuidString + ".png")
                    try (png as Data).write(to: file, options: .atomic)
                    emit(["edited": file.path])
                } catch { emit(["error": error.localizedDescription]) }
            }
        }
    }
}
if CommandLine.arguments.count != 3 { emit(["error":"Expected source and return folder"]); exit(1) }
let bridge = Bridge(source: CommandLine.arguments[1], destination: CommandLine.arguments[2])
bridge.start()
Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { _ in if getppid() == 1 { exit(0) } }
RunLoop.main.run()
