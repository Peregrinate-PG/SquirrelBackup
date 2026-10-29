#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <AVFoundation/AVFoundation.h>
#include <iostream>
int main(int argc,const char* argv[]){
 if(argc!=3)return 2;
 @autoreleasepool{
 NSURL* url=[NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]]];
 NSString* output=[NSString stringWithUTF8String:argv[2]];
 [[NSFileManager defaultManager]createDirectoryAtPath:output withIntermediateDirectories:YES attributes:nil error:nil];
 AVAsset* asset=[AVURLAsset URLAssetWithURL:url options:@{AVURLAssetPreferPreciseDurationAndTimingKey:@YES}];
 NSArray* tracks=[asset tracksWithMediaType:AVMediaTypeVideo];if(tracks.count!=1)return 3;
 AVAssetTrack* track=tracks.firstObject;
 NSError* error=nil;
 AVAssetReader* reader=[[AVAssetReader alloc]initWithAsset:asset error:&error];
 AVAssetReaderTrackOutput* raw=[[AVAssetReaderTrackOutput alloc]initWithTrack:track
 outputSettings:@{(id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_32BGRA)}];
 [reader addOutput:raw];if(![reader startReading])return 4;
 int count=0;double last=-1;
 while(true){@autoreleasepool{
 CMSampleBufferRef sample=[raw copyNextSampleBuffer];if(!sample)break;
 double at=CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sample));
 if(at<last)return 5;last=at;++count;CFRelease(sample);
 }}
 BOOL decoded=reader.status==AVAssetReaderStatusCompleted;
 AVAssetImageGenerator* generator=[[AVAssetImageGenerator alloc]initWithAsset:asset];
 generator.appliesPreferredTrackTransform=YES;
 NSMutableArray* samples=[NSMutableArray array];
 for(int t:{0,7,18,27,37,49,57,65,78,88,98,106,112}){
 CMTime actual;CGImageRef image=[generator copyCGImageAtTime:CMTimeMake(t,1) actualTime:&actual error:&error];
 if(!image)return 6;
 NSBitmapImageRep* rep=[[NSBitmapImageRep alloc]initWithCGImage:image];
 [[rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}]
 writeToFile:[output stringByAppendingPathComponent:[NSString stringWithFormat:@"video-%03d.png",t]] atomically:YES];
 [samples addObject:@(CMTimeGetSeconds(actual))];CGImageRelease(image);
 }
 NSDictionary* result=@{@"passed":@(decoded),@"duration_seconds":@(CMTimeGetSeconds(asset.duration)),
 @"width":@(track.naturalSize.width),@"height":@(track.naturalSize.height),@"decoded_frames":@(count),
 @"last_timestamp":@(last),@"audio_tracks":@([asset tracksWithMediaType:AVMediaTypeAudio].count),@"sample_times":samples};
 NSData* json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
 [json writeToFile:[output stringByAppendingPathComponent:@"video-validation.json"] atomically:YES];
 std::cout<<[[[NSString alloc]initWithData:json encoding:NSUTF8StringEncoding]UTF8String]<<"\n";
 return decoded?0:7;
 }
}
